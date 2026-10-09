import { invoke } from '@tauri-apps/api/core';

/** One file or folder as the Rust `list_dir` command returns it. */
export interface DirEntry {
  name: string;
  /** Relative to the workspace root, with `/` separators; the file commands accept it as is. */
  path: string;
  is_dir: boolean;
  /** Bytes; null for folders and unreadable entries. */
  size: number | null;
  /** Last modification in milliseconds since the Unix epoch, when the platform reports it. */
  modified: number | null;
}

/** One folder level: folders first, then files, by name ignoring case. `.git` and `node_modules` are left out. */
export interface DirListing {
  /** The listed folder relative to the workspace root ('' for the root). */
  path: string;
  entries: DirEntry[];
  /** Visible entries in the folder; more than `entries.length` when Rust capped the listing. */
  total: number;
  truncated: boolean;
}

/** `list_dir` path of the workspace root. */
export const ROOT_DIR = '';

/** Lists one folder level of the open workspace. Rejects with the command's error (outside the workspace, missing...). */
export function listDir(path: string): Promise<DirListing> {
  return invoke<DirListing>('list_dir', { path });
}

/** A folder's listing state. `request` identifies the latest `list_dir` call made for it. */
export type DirState =
  | { status: 'loading'; request: number; listing: DirListing | null }
  | { status: 'loaded'; request: number; listing: DirListing; stale: boolean }
  | { status: 'error'; request: number; error: string };

/** Folders are listed lazily, the first time they are shown expanded; state is keyed by folder path. */
export interface TreeState {
  dirs: Record<string, DirState>;
  expanded: Record<string, boolean>;
}

export type TreeAction =
  | { type: 'toggled'; path: string }
  | { type: 'refreshed' }
  | { type: 'loadStarted'; path: string; request: number }
  | { type: 'loadSucceeded'; path: string; request: number; listing: DirListing }
  | { type: 'loadFailed'; path: string; request: number; error: string };

export const emptyTree: TreeState = { dirs: {}, expanded: {} };

export function fileTreeReducer(state: TreeState, action: TreeAction): TreeState {
  switch (action.type) {
    case 'toggled': {
      const opening = !state.expanded[action.path];
      const expanded = { ...state.expanded, [action.path]: opening };
      // Reopening a folder whose listing failed lists it again.
      if (opening && state.dirs[action.path]?.status === 'error') {
        const dirs = { ...state.dirs };
        delete dirs[action.path];
        return { dirs, expanded };
      }
      return { ...state, expanded };
    }
    case 'refreshed': {
      // Listed folders keep their entries on screen until the new listing arrives; failures are retried.
      const dirs: Record<string, DirState> = {};
      for (const [path, dir] of Object.entries(state.dirs)) {
        if (dir.status === 'loaded') dirs[path] = { ...dir, stale: true };
        else if (dir.status === 'loading') dirs[path] = dir;
      }
      return { ...state, dirs };
    }
    case 'loadStarted': {
      const previous = state.dirs[action.path];
      const listing = previous && previous.status !== 'error' ? previous.listing : null;
      return {
        ...state,
        dirs: { ...state.dirs, [action.path]: { status: 'loading', request: action.request, listing } },
      };
    }
    case 'loadSucceeded':
    case 'loadFailed': {
      // Only the latest request for a folder counts: a slower reply to an earlier one is dropped.
      if (state.dirs[action.path]?.request !== action.request) return state;
      const dir: DirState =
        action.type === 'loadSucceeded'
          ? { status: 'loaded', request: action.request, listing: action.listing, stale: false }
          : { status: 'error', request: action.request, error: action.error };
      return { ...state, dirs: { ...state.dirs, [action.path]: dir } };
    }
  }
}

/** Whether a shown folder must be listed: never listed, or stale after a refresh. Failures wait for a retry. */
export function needsLoad(dir: DirState | undefined): boolean {
  return dir === undefined || (dir.status === 'loaded' && dir.stale);
}

/** Footer for a capped folder, or null when every entry is shown. */
export function truncationNotice(listing: DirListing): string | null {
  return listing.truncated ? `Mostrando ${listing.entries.length} de ${listing.total} elementos.` : null;
}

/** The folder name of a workspace root, for any path style (`\\?\D:\a\b`, `C:\a\b\`, `/a/b`). */
export function workspaceName(root: string): string {
  return root.split(/[\\/]+/).filter(Boolean).pop() ?? root;
}
