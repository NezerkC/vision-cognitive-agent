import { beforeEach, describe, expect, it, vi } from 'vitest';

/** A plain stub for the plugin's `open`, so each test decides the picker's answer. */
const dialog = vi.hoisted(() => ({
  open: null as null | ((options: unknown) => Promise<unknown>),
  calls: [] as unknown[],
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: (options: unknown) => {
    dialog.calls.push(options);
    if (!dialog.open) throw new Error('no picker answer configured for this test');
    return dialog.open(options);
  },
}));

import { pickWorkspaceFolder } from './workspaceDialog';

describe('pickWorkspaceFolder', () => {
  beforeEach(() => {
    dialog.open = null;
    dialog.calls = [];
  });

  it('asks the native picker for one folder and returns it', async () => {
    dialog.open = async () => 'D:\\projects\\mi-app';

    await expect(pickWorkspaceFolder()).resolves.toBe('D:\\projects\\mi-app');
    expect(dialog.calls).toEqual([expect.objectContaining({ directory: true, multiple: false })]);
  });

  it('resolves null when the user cancels', async () => {
    dialog.open = async () => null;

    await expect(pickWorkspaceFolder()).resolves.toBeNull();
  });

  it('rejects with the picker error instead of falling back to another folder', async () => {
    dialog.open = async () => {
      throw new Error('dialog unavailable');
    };

    await expect(pickWorkspaceFolder()).rejects.toThrow('dialog unavailable');
  });

  it('rejects when the picker answers with more than one path', async () => {
    dialog.open = async () => ['D:\\a', 'D:\\b'];

    await expect(pickWorkspaceFolder()).rejects.toThrow('no devolvió una carpeta válida');
  });
});
