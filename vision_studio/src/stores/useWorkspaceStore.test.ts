import { beforeEach, describe, expect, it } from 'vitest';
import { useWorkspaceStore } from './useWorkspaceStore';

describe('useWorkspaceStore', () => {
  beforeEach(() => useWorkspaceStore.setState({ root: null, error: null }));

  it('keeps the root Rust confirmed', () => {
    useWorkspaceStore.getState().opened('\\\\?\\D:\\ws');

    expect(useWorkspaceStore.getState()).toMatchObject({ root: '\\\\?\\D:\\ws', error: null });
  });

  it('drops the previous root when a folder cannot be opened', () => {
    useWorkspaceStore.getState().opened('\\\\?\\D:\\ws');
    useWorkspaceStore.getState().failed('La carpeta no existe: D:\\nope');

    expect(useWorkspaceStore.getState()).toMatchObject({ root: null, error: 'La carpeta no existe: D:\\nope' });
  });
});
