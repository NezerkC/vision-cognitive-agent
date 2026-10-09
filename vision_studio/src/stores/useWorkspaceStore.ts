import { create } from 'zustand';

/**
 * The workspace Rust accepted through `set_workspace`. File commands only act inside `root`, so views that list or
 * read files wait for it instead of using the requested path in the settings.
 */
interface WorkspaceState {
  /** Canonical root returned by `set_workspace`; null until it answers or when the folder could not be opened. */
  root: string | null;
  /** Why the requested folder could not be opened. */
  error: string | null;
  opened: (root: string) => void;
  failed: (error: string) => void;
}

export const useWorkspaceStore = create<WorkspaceState>()((set) => ({
  root: null,
  error: null,
  opened: (root) => set({ root, error: null }),
  failed: (error) => set({ root: null, error }),
}));
