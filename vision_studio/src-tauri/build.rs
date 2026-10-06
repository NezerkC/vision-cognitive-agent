// Every app command gets generated `allow-<command>` / `deny-<command>` permissions, so a window can only call
// the commands its capability file grants (capabilities/default.json).
const APP_COMMANDS: &[&str] = &[
    "web_search_duckduckgo",
    "set_workspace",
    "read_file_content",
    "write_file_content",
    "execute_powershell_command",
];

fn main() {
    tauri_build::try_build(
        tauri_build::Attributes::new()
            .app_manifest(tauri_build::AppManifest::new().commands(APP_COMMANDS)),
    )
    .expect("failed to run tauri-build");
}
