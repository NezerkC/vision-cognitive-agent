import { beforeEach, describe, expect, it, vi } from 'vitest';
import { invoke } from '@tauri-apps/api/core';
import {
  DirListing,
  ROOT_DIR,
  TreeState,
  emptyTree,
  fileTreeReducer,
  listDir,
  needsLoad,
  truncationNotice,
  workspaceName,
} from './fileTree';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));

function listing(path: string, names: string[] = [], total = names.length): DirListing {
  return {
    path,
    entries: names.map((name) => ({
      name,
      path: path ? `${path}/${name}` : name,
      is_dir: false,
      size: 1,
      modified: 0,
    })),
    total,
    truncated: total > names.length,
  };
}

function loaded(path: string, dirListing: DirListing, request = 1): TreeState {
  const tree = fileTreeReducer(emptyTree, { type: 'loadStarted', path, request });
  return fileTreeReducer(tree, { type: 'loadSucceeded', path, request, listing: dirListing });
}

describe('listDir', () => {
  beforeEach(() => vi.mocked(invoke).mockReset());

  it('lists one folder through the Rust list_dir command', async () => {
    const src = listing('src', ['main.py']);
    vi.mocked(invoke).mockResolvedValue(src);

    await expect(listDir('src')).resolves.toEqual(src);
    expect(invoke).toHaveBeenCalledWith('list_dir', { path: 'src' });
  });
});

describe('fileTreeReducer', () => {
  it('marks a folder as loading, then stores the listing its request returned', () => {
    let tree = fileTreeReducer(emptyTree, { type: 'loadStarted', path: ROOT_DIR, request: 1 });
    expect(tree.dirs[ROOT_DIR]).toEqual({ status: 'loading', request: 1, listing: null });

    const root = listing(ROOT_DIR, ['README.md']);
    tree = fileTreeReducer(tree, { type: 'loadSucceeded', path: ROOT_DIR, request: 1, listing: root });
    expect(tree.dirs[ROOT_DIR]).toEqual({ status: 'loaded', request: 1, listing: root, stale: false });
  });

  it('stores the error of a failed listing', () => {
    let tree = fileTreeReducer(emptyTree, { type: 'loadStarted', path: 'src', request: 1 });
    tree = fileTreeReducer(tree, { type: 'loadFailed', path: 'src', request: 1, error: 'La ruta no existe: src' });

    expect(tree.dirs.src).toEqual({ status: 'error', request: 1, error: 'La ruta no existe: src' });
  });

  it('drops replies to an older request for the same folder', () => {
    let tree = fileTreeReducer(emptyTree, { type: 'loadStarted', path: 'src', request: 1 });
    tree = fileTreeReducer(tree, { type: 'loadStarted', path: 'src', request: 2 });
    const latest = tree;

    tree = fileTreeReducer(tree, { type: 'loadSucceeded', path: 'src', request: 1, listing: listing('src', ['old.py']) });
    tree = fileTreeReducer(tree, { type: 'loadFailed', path: 'src', request: 1, error: 'old error' });
    tree = fileTreeReducer(tree, { type: 'loadSucceeded', path: 'docs', request: 1, listing: listing('docs') });

    expect(tree).toBe(latest);
  });

  it('keeps showing the previous entries while a folder reloads', () => {
    const src = listing('src', ['a.py']);
    const tree = fileTreeReducer(loaded('src', src), { type: 'loadStarted', path: 'src', request: 2 });

    expect(tree.dirs.src).toEqual({ status: 'loading', request: 2, listing: src });
  });

  it('expands and collapses folders, and lists a failed folder again when it is reopened', () => {
    let tree = fileTreeReducer(emptyTree, { type: 'toggled', path: 'src' });
    expect(tree.expanded.src).toBe(true);

    tree = fileTreeReducer(tree, { type: 'loadStarted', path: 'src', request: 1 });
    tree = fileTreeReducer(tree, { type: 'loadFailed', path: 'src', request: 1, error: 'Acceso denegado' });
    tree = fileTreeReducer(tree, { type: 'toggled', path: 'src' });
    expect(tree.expanded.src).toBe(false);

    tree = fileTreeReducer(tree, { type: 'toggled', path: 'src' });
    expect(tree.expanded.src).toBe(true);
    expect(needsLoad(tree.dirs.src)).toBe(true);
  });

  it('on refresh marks listed folders stale, keeping their entries, and forgets failures', () => {
    const src = listing('src', ['a.py']);
    let tree = loaded('src', src);
    tree = fileTreeReducer(tree, { type: 'loadStarted', path: 'docs', request: 2 });
    tree = fileTreeReducer(tree, { type: 'loadFailed', path: 'docs', request: 2, error: 'Acceso denegado' });
    tree = fileTreeReducer(tree, { type: 'loadStarted', path: 'lib', request: 3 });
    const libLoading = tree.dirs.lib;

    tree = fileTreeReducer(tree, { type: 'refreshed' });

    expect(tree.dirs.src).toEqual({ status: 'loaded', request: 1, listing: src, stale: true });
    expect(tree.dirs.docs).toBeUndefined();
    expect(tree.dirs.lib).toBe(libLoading);
  });
});

describe('needsLoad', () => {
  it('lists folders never listed or refreshed, and never retries a failure on its own', () => {
    expect(needsLoad(undefined)).toBe(true);
    expect(needsLoad({ status: 'loading', request: 1, listing: null })).toBe(false);
    expect(needsLoad({ status: 'loaded', request: 1, listing: listing('src'), stale: false })).toBe(false);
    expect(needsLoad({ status: 'loaded', request: 1, listing: listing('src'), stale: true })).toBe(true);
    expect(needsLoad({ status: 'error', request: 1, error: 'Acceso denegado' })).toBe(false);
  });
});

describe('truncationNotice', () => {
  it('says how many entries a capped folder shows', () => {
    expect(truncationNotice(listing('big', ['a', 'b'], 5321))).toBe('Mostrando 2 de 5321 elementos.');
    expect(truncationNotice(listing('small', ['a', 'b']))).toBeNull();
  });
});

describe('workspaceName', () => {
  it('names the workspace after its folder, whatever the path style', () => {
    expect(workspaceName('\\\\?\\D:\\projects\\vision')).toBe('vision');
    expect(workspaceName('\\\\?\\UNC\\server\\share\\repo')).toBe('repo');
    expect(workspaceName('C:\\proyectos\\mi-app\\')).toBe('mi-app');
    expect(workspaceName('/home/ana/repo')).toBe('repo');
  });
});
