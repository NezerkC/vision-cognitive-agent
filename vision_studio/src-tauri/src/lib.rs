use scraper::{Html, Selector};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use std::process::Command;

#[derive(Debug, Serialize, Deserialize)]
pub struct ExecutionResult {
    pub stdout: String,
    pub stderr: String,
    pub exit_code: i32,
}

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
async fn read_file_content(path: String) -> Result<String, String> {
    let file_path = Path::new(&path);
    if !file_path.exists() {
        return Err(format!("El archivo no existe: {}", path));
    }
    fs::read_to_string(file_path).map_err(|e| format!("Error al leer archivo: {}", e))
}

#[tauri::command]
async fn write_file_content(path: String, content: String) -> Result<String, String> {
    let file_path = Path::new(&path);
    if let Some(parent) = file_path.parent() {
        if !parent.exists() {
            fs::create_dir_all(parent).map_err(|e| format!("Error al crear directorios padres: {}", e))?;
        }
    }
    fs::write(file_path, content).map_err(|e| format!("Error al escribir archivo: {}", e))?;
    Ok(format!("Archivo guardado correctamente en: {}", path))
}

#[tauri::command]
async fn execute_powershell_command(command: String, cwd: Option<String>) -> Result<ExecutionResult, String> {
    let mut cmd = Command::new("powershell.exe");
    cmd.args(["-NoProfile", "-NonInteractive", "-Command", &command]);

    if let Some(work_dir) = cwd {
        if !work_dir.is_empty() {
            cmd.current_dir(work_dir);
        }
    }

    let output = cmd.output().map_err(|e| format!("Error al ejecutar comando PowerShell: {}", e))?;

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
    
    let res = client.post("https://lite.duckduckgo.com/lite/")
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
        .invoke_handler(tauri::generate_handler![
            greet, 
            web_search_duckduckgo,
            read_file_content,
            write_file_content,
            execute_powershell_command
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
