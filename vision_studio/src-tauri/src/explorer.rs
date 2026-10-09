//! Lazy folder listing for the Vision Studio explorer: one level per call, confined to the workspace.

use serde::Serialize;
use std::fs;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::workspace::{resolve_existing, workspace_relative};

/// Most entries one `list_dir` call returns, so a huge folder cannot flood the webview.
pub const MAX_DIR_ENTRIES: usize = 2000;

/// Entries the explorer never shows: version-control internals and installed dependencies. Other dotfiles are shown.
/// Only listings skip them; an explicit path inside them still lists.
const HIDDEN_NAMES: [&str; 2] = [".git", "node_modules"];

/// One file or folder in a listing.
#[derive(Debug, Serialize)]
pub struct DirEntryInfo {
    pub name: String,
    /// Relative to the workspace root, with `/` separators: pass it back to `list_dir` or the file commands.
    pub path: String,
    pub is_dir: bool,
    /// Bytes; `None` for folders and for entries whose metadata cannot be read.
    pub size: Option<u64>,
    /// Last modification in milliseconds since the Unix epoch, when the platform reports it.
    pub modified: Option<u64>,
}

/// One level of a folder.
#[derive(Debug, Serialize)]
pub struct DirListing {
    /// The listed folder relative to the workspace root (`""` for the root).
    pub path: String,
    /// Folders first, then files, each group sorted by name ignoring case.
    pub entries: Vec<DirEntryInfo>,
    /// Visible entries in the folder: more than `entries.len()` when the listing was truncated.
    pub total: usize,
    pub truncated: bool,
}

/// A visible entry before the cap, kept small: metadata is read only for the entries that are returned.
struct Visible {
    is_dir: bool,
    sort_key: String,
    name: String,
}

/// Lists one level of `requested` (relative to `root` or absolute inside it; `""` is the root).
pub fn list_dir(root: &Path, requested: &str, max_entries: usize) -> Result<DirListing, String> {
    let requested = if requested.is_empty() { "." } else { requested };
    let dir = resolve_existing(root, requested)?;
    if !dir.is_dir() {
        return Err(format!("No es una carpeta: {requested}"));
    }
    let mut visible =
        read_visible(&dir).map_err(|e| format!("No se pudo leer la carpeta {requested}: {e}"))?;
    // Folders first, then by name ignoring case; the exact name breaks ties so the order is stable.
    visible
        .sort_by(|a, b| (!a.is_dir, &a.sort_key, &a.name).cmp(&(!b.is_dir, &b.sort_key, &b.name)));
    let total = visible.len();
    visible.truncate(max_entries);

    let path = workspace_relative(root, &dir)?;
    let entries = visible
        .into_iter()
        .map(|entry| entry_info(&dir, &path, entry))
        .collect();
    Ok(DirListing {
        path,
        entries,
        total,
        truncated: total > max_entries,
    })
}

/// The entries of `dir` except the hidden names. A name that is not valid Unicode is kept, shown lossily.
fn read_visible(dir: &Path) -> std::io::Result<Vec<Visible>> {
    let mut visible = Vec::new();
    for item in fs::read_dir(dir)? {
        let item = item?;
        let name = item.file_name().to_string_lossy().into_owned();
        if HIDDEN_NAMES.contains(&name.as_str()) {
            continue;
        }
        let file_type = item.file_type()?;
        // A link (or junction) to a folder expands like one; a broken link shows as a file.
        let is_dir = if file_type.is_symlink() {
            fs::metadata(item.path()).is_ok_and(|m| m.is_dir())
        } else {
            file_type.is_dir()
        };
        visible.push(Visible {
            is_dir,
            sort_key: name.to_lowercase(),
            name,
        });
    }
    Ok(visible)
}

/// The returned form of an entry of `dir`, whose workspace-relative path is `parent`.
fn entry_info(dir: &Path, parent: &str, Visible { is_dir, name, .. }: Visible) -> DirEntryInfo {
    let metadata = fs::metadata(dir.join(&name)).ok();
    DirEntryInfo {
        path: if parent.is_empty() {
            name.clone()
        } else {
            format!("{parent}/{name}")
        },
        size: metadata.as_ref().filter(|_| !is_dir).map(|m| m.len()),
        modified: metadata
            .and_then(|m| m.modified().ok())
            .and_then(epoch_millis),
        name,
        is_dir,
    }
}

fn epoch_millis(time: SystemTime) -> Option<u64> {
    let millis = time.duration_since(UNIX_EPOCH).ok()?.as_millis();
    u64::try_from(millis).ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::PathBuf;

    /// A workspace with a nested folder, dotfiles, `.git`/`node_modules`, and a sibling folder outside it.
    fn workspace() -> (tempfile::TempDir, PathBuf) {
        let dir = tempfile::tempdir().unwrap();
        let root = dir.path().join("ws");
        fs::create_dir_all(root.join("src").join("nested")).unwrap();
        fs::write(root.join("src").join("main.py"), "x = 1").unwrap();
        // A worktree or submodule has a `.git` file instead of a folder.
        fs::write(root.join("src").join(".git"), "gitdir: ../.git").unwrap();
        fs::create_dir_all(root.join(".git").join("objects")).unwrap();
        fs::create_dir_all(root.join("node_modules").join("react")).unwrap();
        fs::create_dir_all(root.join(".github")).unwrap();
        fs::create_dir_all(root.join("Zeta")).unwrap();
        fs::create_dir_all(root.join("alpha")).unwrap();
        fs::write(root.join(".env"), "KEY=1").unwrap();
        fs::write(root.join("b.txt"), "b").unwrap();
        fs::write(root.join("A.md"), "a").unwrap();
        fs::create_dir_all(dir.path().join("outside")).unwrap();
        let root = fs::canonicalize(&root).unwrap();
        (dir, root)
    }

    fn names(listing: &DirListing) -> Vec<&str> {
        listing.entries.iter().map(|e| e.name.as_str()).collect()
    }

    fn entry<'a>(listing: &'a DirListing, name: &str) -> &'a DirEntryInfo {
        listing.entries.iter().find(|e| e.name == name).unwrap()
    }

    #[test]
    fn lists_folders_first_then_files_ignoring_case() {
        let (_dir, root) = workspace();
        let listing = list_dir(&root, "", MAX_DIR_ENTRIES).unwrap();
        assert_eq!(
            names(&listing),
            [".github", "alpha", "src", "Zeta", ".env", "A.md", "b.txt"]
        );
    }

    #[test]
    fn hides_git_and_node_modules_but_shows_other_dotfiles() {
        let (_dir, root) = workspace();
        let top = list_dir(&root, "", MAX_DIR_ENTRIES).unwrap();
        assert!(!names(&top).contains(&".git"));
        assert!(!names(&top).contains(&"node_modules"));
        assert!(names(&top).contains(&".github") && names(&top).contains(&".env"));
        assert_eq!(top.total, 7);
        let src = list_dir(&root, "src", MAX_DIR_ENTRIES).unwrap();
        assert!(!names(&src).contains(&".git"));
    }

    #[test]
    fn lists_one_level_with_paths_relative_to_the_workspace() {
        let (_dir, root) = workspace();
        let top = list_dir(&root, "", MAX_DIR_ENTRIES).unwrap();
        assert_eq!(top.path, "");
        assert_eq!(entry(&top, "src").path, "src");
        assert!(entry(&top, "src").is_dir);

        let src = list_dir(&root, "src", MAX_DIR_ENTRIES).unwrap();
        assert_eq!(src.path, "src");
        let found: Vec<(&str, &str, bool)> = src
            .entries
            .iter()
            .map(|e| (e.name.as_str(), e.path.as_str(), e.is_dir))
            .collect();
        assert_eq!(
            found,
            [
                ("nested", "src/nested", true),
                ("main.py", "src/main.py", false)
            ]
        );

        let nested = list_dir(&root, "src/nested", MAX_DIR_ENTRIES).unwrap();
        assert_eq!(nested.path, "src/nested");
        assert!(nested.entries.is_empty());
    }

    #[test]
    fn accepts_the_root_as_dot_and_absolute_paths_inside() {
        let (_dir, root) = workspace();
        assert_eq!(list_dir(&root, ".", MAX_DIR_ENTRIES).unwrap().path, "");
        let absolute = root.join("src");
        let src = list_dir(&root, absolute.to_str().unwrap(), MAX_DIR_ENTRIES).unwrap();
        assert_eq!(src.path, "src");
        assert_eq!(entry(&src, "main.py").path, "src/main.py");
    }

    #[test]
    fn caps_the_entries_and_reports_truncation() {
        let (_dir, root) = workspace();
        let capped = list_dir(&root, "", 3).unwrap();
        assert_eq!(names(&capped), [".github", "alpha", "src"]);
        assert_eq!(capped.total, 7);
        assert!(capped.truncated);

        let full = list_dir(&root, "", 7).unwrap();
        assert_eq!(full.entries.len(), 7);
        assert!(!full.truncated);
    }

    #[test]
    fn rejects_paths_outside_the_workspace() {
        let (dir, root) = workspace();
        let outside = dir.path().join("outside");
        for requested in ["../outside", outside.to_str().unwrap(), "src/../.."] {
            let error = list_dir(&root, requested, MAX_DIR_ENTRIES).unwrap_err();
            assert!(error.contains("fuera del proyecto"), "{requested}: {error}");
        }
    }

    #[test]
    fn rejects_files_and_missing_folders() {
        let (_dir, root) = workspace();
        let file = list_dir(&root, "src/main.py", MAX_DIR_ENTRIES).unwrap_err();
        assert!(file.contains("No es una carpeta"), "{file}");
        let missing = list_dir(&root, "missing", MAX_DIR_ENTRIES).unwrap_err();
        assert!(missing.contains("no existe"), "{missing}");
    }

    #[test]
    fn reports_file_size_and_modification_time() {
        let (_dir, root) = workspace();
        let src = list_dir(&root, "src", MAX_DIR_ENTRIES).unwrap();
        let main = entry(&src, "main.py");
        assert_eq!(main.size, Some(5));
        // Written just now, so after 2020-09-13 in milliseconds.
        assert!(main.modified.unwrap() > 1_600_000_000_000);
        assert_eq!(entry(&src, "nested").size, None);
    }

    #[test]
    fn links_to_folders_list_as_folders_and_cannot_escape_the_workspace() {
        let (dir, root) = workspace();
        if !make_dir_link(&dir.path().join("outside"), &root.join("escape"))
            || !make_dir_link(&root.join("src"), &root.join("src-link"))
            || !make_dir_link(&root.join("gone"), &root.join("broken"))
        {
            eprintln!("skipped: this account cannot create folder links");
            return;
        }
        let top = list_dir(&root, "", MAX_DIR_ENTRIES).unwrap();
        assert!(entry(&top, "escape").is_dir);
        assert!(entry(&top, "src-link").is_dir);
        assert!(!entry(&top, "broken").is_dir);

        let escape = list_dir(&root, "escape", MAX_DIR_ENTRIES).unwrap_err();
        assert!(escape.contains("fuera del proyecto"), "{escape}");
        // A link inside the workspace lists its target, under the target's canonical path.
        let linked = list_dir(&root, "src-link", MAX_DIR_ENTRIES).unwrap();
        assert_eq!(linked.path, "src");
        assert_eq!(entry(&linked, "main.py").path, "src/main.py");
    }

    #[cfg(windows)]
    fn make_dir_link(target: &Path, link: &Path) -> bool {
        std::os::windows::fs::symlink_dir(target, link).is_ok()
    }

    #[cfg(unix)]
    fn make_dir_link(target: &Path, link: &Path) -> bool {
        std::os::unix::fs::symlink(target, link).is_ok()
    }
}
