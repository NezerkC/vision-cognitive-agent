use scraper::{Html, Selector};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use std::process::Command;
use tauri::{AppHandle, State};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};

mod workspace;

use workspace::{
    resolve_existing, resolve_for_write, validate_workspace_root, WorkspaceState, MAX_READ_BYTES,
};

#[derive(Debug, Serialize, Deserialize)]
pub struct ExecutionResult {
    pub stdout: String,
    pub stderr: String,
    pub exit_code: i32,
}

/// Opens a folder as the workspace. File and shell commands are confined to it afterwards.
#[tauri::command]
fn set_workspace(state: State<'_, WorkspaceState>, path: String) -> Result<String, String> {
    let root = validate_workspace_root(Path::new(&path))?;
    let shown = root.display().to_string();
    *state
        .0
        .lock()
        .map_err(|_| "Estado del proyecto no disponible.".to_string())? = Some(root);
    Ok(shown)
}

#[tauri::command]
async fn read_file_content(
    state: State<'_, WorkspaceState>,
    path: String,
) -> Result<String, String> {
    let file_path = resolve_existing(&state.root()?, &path)?;
    let size = fs::metadata(&file_path)
        .map_err(|e| format!("Error al leer archivo: {}", e))?
        .len();
    if size > MAX_READ_BYTES {
        return Err(format!(
            "El archivo pesa {} bytes y supera el límite de {} bytes.",
            size, MAX_READ_BYTES
        ));
    }
    fs::read_to_string(&file_path).map_err(|e| format!("Error al leer archivo: {}", e))
}

#[tauri::command]
async fn write_file_content(
    state: State<'_, WorkspaceState>,
    path: String,
    content: String,
) -> Result<String, String> {
    let file_path = resolve_for_write(&state.root()?, &path)?;
    if let Some(parent) = file_path.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| format!("Error al crear directorios padres: {}", e))?;
    }
    fs::write(&file_path, content).map_err(|e| format!("Error al escribir archivo: {}", e))?;
    Ok(format!(
        "Archivo guardado correctamente en: {}",
        file_path.display()
    ))
}

/// Runs a PowerShell command inside the workspace after the user confirms it in a native dialog.
/// The confirmation happens in Rust so script injected into the webview cannot skip it.
#[tauri::command]
async fn execute_powershell_command(
    app: AppHandle,
    state: State<'_, WorkspaceState>,
    command: String,
    cwd: Option<String>,
) -> Result<ExecutionResult, String> {
    let root = state.root()?;
    let work_dir = match cwd.filter(|c| !c.is_empty()) {
        Some(dir) => resolve_existing(&root, &dir)?,
        None => root,
    };
    if !work_dir.is_dir() {
        return Err(format!(
            "El directorio de trabajo no es una carpeta: {}",
            work_dir.display()
        ));
    }

    let prompt = format!(
        "Vision Studio quiere ejecutar este comando de PowerShell:\n\n{}\n\nCarpeta: {}",
        command,
        work_dir.display()
    );
    let dialog_app = app.clone();
    let approved = tauri::async_runtime::spawn_blocking(move || {
        dialog_app
            .dialog()
            .message(prompt)
            .title("Confirmar comando")
            .kind(MessageDialogKind::Warning)
            .buttons(MessageDialogButtons::OkCancelCustom(
                "Ejecutar".into(),
                "Cancelar".into(),
            ))
            .blocking_show()
    })
    .await
    .map_err(|e| format!("No se pudo mostrar la confirmación: {}", e))?;
    if !approved {
        return Err("El usuario rechazó la ejecución del comando.".to_string());
    }

    let mut cmd = Command::new("powershell.exe");
    cmd.args(["-NoProfile", "-NonInteractive", "-Command", &command]);
    cmd.current_dir(&work_dir);

    let output = cmd
        .output()
        .map_err(|e| format!("Error al ejecutar comando PowerShell: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let exit_code = output.status.code().unwrap_or(-1);

    Ok(ExecutionResult {
        stdout,
        stderr,
        exit_code,
    })
}

#[tauri::command]
async fn web_search_duckduckgo(query: String) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        .build()
        .map_err(|e| e.to_string())?;

    let res = client
        .post("https://lite.duckduckgo.com/lite/")
        .form(&[("q", &query)])
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let body = res.text().await.map_err(|e| e.to_string())?;

    let document = Html::parse_document(&body);
    let snippet_selector = Selector::parse(".result-snippet").unwrap();

    let mut results = String::from("Resultados de búsqueda en DuckDuckGo:\n");
    let mut found = false;
    let mut count = 0;

    for element in document.select(&snippet_selector) {
        if count >= 5 {
            break;
        }
        let text = element.text().collect::<Vec<_>>().join(" ");
        let text = text.trim();
        if !text.is_empty() {
            results.push_str(&format!("- {}\n", text));
            found = true;
            count += 1;
        }
    }

    if !found {
        return Ok("No se encontraron resultados relevantes.".to_string());
    }

    Ok(results)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(WorkspaceState::default())
        .invoke_handler(tauri::generate_handler![
            web_search_duckduckgo,
            set_workspace,
            read_file_content,
            write_file_content,
            execute_powershell_command
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
