/** How many recently opened folders the sidebar keeps. */
export const MAX_RECENT_FOLDERS = 8;

/**
 * The folder older builds hardcoded as the default workspace. It was never chosen by the user, so it is removed from
 * settings that were persisted with it.
 */
const LEGACY_DEFAULT_FOLDER = 'C:\\Users\\lolpl\\Desktop\\02_Proyectos_Dev\\vision-cognitive-agent';

export interface WorkspacePreferences {
  currentWorkspacePath: string;
  recentProjects: string[];
}

/** Moves `path` to the front of the recent list, without duplicates, keeping at most `MAX_RECENT_FOLDERS`. */
export function addRecentFolder(recent: string[], path: string): string[] {
  const others = recent.filter((entry) => entry !== path);
  return [path, ...others].slice(0, MAX_RECENT_FOLDERS);
}

/** Settings stored before the native picker: drops the hardcoded default and any malformed value. */
export function migrateWorkspacePreferences(stored: Record<string, unknown>): WorkspacePreferences {
  const storedPath = typeof stored.currentWorkspacePath === 'string' ? stored.currentWorkspacePath : '';
  const storedRecent = Array.isArray(stored.recentProjects) ? stored.recentProjects : [];

  return {
    currentWorkspacePath: storedPath === LEGACY_DEFAULT_FOLDER ? '' : storedPath,
    recentProjects: storedRecent.filter(
      (entry): entry is string => typeof entry === 'string' && entry !== LEGACY_DEFAULT_FOLDER,
    ),
  };
}
