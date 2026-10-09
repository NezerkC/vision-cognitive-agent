import { open } from '@tauri-apps/plugin-dialog';

/**
 * Asks the user for a workspace folder with the native picker. Resolves null when the user cancels. The picker runs in
 * the plugin's async IPC, so no Rust thread blocks while the dialog is open; Rust checks the chosen path when
 * `set_workspace` receives it.
 */
export async function pickWorkspaceFolder(): Promise<string | null> {
  const selected = await open({ directory: true, multiple: false, title: 'Abrir carpeta del proyecto' });
  if (selected === null) return null;
  if (typeof selected !== 'string') throw new Error('El selector no devolvió una carpeta válida.');
  return selected;
}
