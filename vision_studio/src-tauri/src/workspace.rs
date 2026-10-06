//! Confines file and shell commands to the workspace the user opened.
//!
//! Every command the webview can invoke is reachable from injected script too, so the checks live here in Rust:
//! paths are canonicalized (resolving `..` and symlinks) and must stay inside the canonical workspace root.

use std::fs;
use std::path::{Component, Path, PathBuf};
use std::sync::Mutex;

/// Largest file `read_file_content` returns, so one call cannot load a huge file into the webview.
pub const MAX_READ_BYTES: u64 = 10 * 1024 * 1024;

/// The canonical root of the workspace opened in Vision Studio, if any.
#[derive(Default)]
pub struct WorkspaceState(pub Mutex<Option<PathBuf>>);

impl WorkspaceState {
    pub fn root(&self) -> Result<PathBuf, String> {
        self.0
            .lock()
            .map_err(|_| "Estado del proyecto no disponible.".to_string())?
            .clone()
            .ok_or_else(|| "No hay un proyecto abierto.".to_string())
    }
}

/// Canonical form of a folder that can be opened as a workspace: an existing directory that is not a filesystem root.
pub fn validate_workspace_root(path: &Path) -> Result<PathBuf, String> {
    let canonical =
        fs::canonicalize(path).map_err(|_| format!("La carpeta no existe: {}", path.display()))?;
    if !canonical.is_dir() {
        return Err(format!("No es una carpeta: {}", path.display()));
    }
    if canonical.parent().is_none() {
        return Err("No se puede abrir la raíz del disco como proyecto.".to_string());
    }
    Ok(canonical)
}

/// Canonical path of an existing file or folder inside `root`. Relative paths are resolved against `root`.
pub fn resolve_existing(root: &Path, requested: &str) -> Result<PathBuf, String> {
    let canonical = fs::canonicalize(absolute_in(root, requested))
        .map_err(|_| format!("La ruta no existe: {requested}"))?;
    if !canonical.starts_with(root) {
        return Err(outside_error(requested));
    }
    Ok(canonical)
}

/// Path where a file may be written inside `root`. The file and its parent folders may not exist yet.
pub fn resolve_for_write(root: &Path, requested: &str) -> Result<PathBuf, String> {
    let joined = absolute_in(root, requested);
    // The nearest existing ancestor is canonicalized (resolving symlinks); the part that does not exist yet
    // may only contain plain names, so it cannot climb back out with `..`.
    let ancestor = joined
        .ancestors()
        .find(|a| a.exists())
        .ok_or_else(|| outside_error(requested))?;
    let base = fs::canonicalize(ancestor).map_err(|_| outside_error(requested))?;
    if !base.starts_with(root) {
        return Err(outside_error(requested));
    }
    let rest = joined
        .strip_prefix(ancestor)
        .map_err(|_| outside_error(requested))?;
    if !rest.components().all(|c| matches!(c, Component::Normal(_))) {
        return Err(outside_error(requested));
    }
    let target = base.join(rest);
    if target.is_dir() {
        return Err(format!("La ruta es una carpeta: {requested}"));
    }
    Ok(target)
}

fn absolute_in(root: &Path, requested: &str) -> PathBuf {
    let path = Path::new(requested);
    if path.is_absolute() {
        path.to_path_buf()
    } else {
        root.join(path)
    }
}

fn outside_error(requested: &str) -> String {
    format!("La ruta está fuera del proyecto abierto: {requested}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn workspace() -> (tempfile::TempDir, PathBuf) {
        let dir = tempfile::tempdir().unwrap();
        let root = dir.path().join("ws");
        fs::create_dir_all(root.join("src")).unwrap();
        fs::write(root.join("src").join("main.py"), "x = 1").unwrap();
        fs::create_dir_all(dir.path().join("outside")).unwrap();
        fs::write(dir.path().join("outside").join("secret.txt"), "s").unwrap();
        let root = fs::canonicalize(&root).unwrap();
        (dir, root)
    }

    #[test]
    fn workspace_root_must_be_an_existing_directory() {
        let (_dir, root) = workspace();
        assert_eq!(validate_workspace_root(&root).unwrap(), root);
        assert!(validate_workspace_root(&root.join("missing")).is_err());
        assert!(validate_workspace_root(&root.join("src").join("main.py")).is_err());
    }

    #[test]
    fn workspace_root_cannot_be_a_filesystem_root() {
        let (_dir, root) = workspace();
        let fs_root = root.ancestors().last().unwrap().to_path_buf();
        assert!(validate_workspace_root(&fs_root).is_err());
    }

    #[test]
    fn resolve_existing_accepts_relative_and_absolute_paths_inside() {
        let (_dir, root) = workspace();
        let expected = root.join("src").join("main.py");
        assert_eq!(resolve_existing(&root, "src/main.py").unwrap(), expected);
        assert_eq!(
            resolve_existing(&root, expected.to_str().unwrap()).unwrap(),
            expected
        );
    }

    #[test]
    fn resolve_existing_rejects_paths_outside() {
        let (dir, root) = workspace();
        let outside = dir.path().join("outside").join("secret.txt");
        assert!(resolve_existing(&root, "../outside/secret.txt").is_err());
        assert!(resolve_existing(&root, outside.to_str().unwrap()).is_err());
        assert!(resolve_existing(&root, "src/missing.py").is_err());
    }

    #[test]
    fn resolve_for_write_allows_new_files_and_folders_inside() {
        let (_dir, root) = workspace();
        assert_eq!(
            resolve_for_write(&root, "src/new.py").unwrap(),
            root.join("src").join("new.py")
        );
        assert_eq!(
            resolve_for_write(&root, "a/b/c.txt").unwrap(),
            root.join("a").join("b").join("c.txt")
        );
        assert_eq!(
            resolve_for_write(&root, "src/main.py").unwrap(),
            root.join("src").join("main.py")
        );
    }

    #[test]
    fn resolve_for_write_rejects_escapes() {
        let (dir, root) = workspace();
        let outside = dir.path().join("outside").join("new.txt");
        assert!(resolve_for_write(&root, "../outside/new.txt").is_err());
        assert!(resolve_for_write(&root, "src/../../outside/new.txt").is_err());
        assert!(resolve_for_write(&root, "newdir/../../outside/new.txt").is_err());
        assert!(resolve_for_write(&root, outside.to_str().unwrap()).is_err());
        assert!(resolve_for_write(&root, "src").is_err());
    }
}
