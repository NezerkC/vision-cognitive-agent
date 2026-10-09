import { describe, expect, it } from 'vitest';
import { MAX_RECENT_FOLDERS, addRecentFolder, migrateWorkspacePreferences } from './recentFolders';

/** The path the app used to hardcode. Stored copies from older builds must not survive. */
const LEGACY_PATH = 'C:\\Users\\lolpl\\Desktop\\02_Proyectos_Dev\\vision-cognitive-agent';

describe('addRecentFolder', () => {
  it('puts the newest folder first and drops its earlier entry', () => {
    expect(addRecentFolder(['D:\\a', 'D:\\b'], 'D:\\b')).toEqual(['D:\\b', 'D:\\a']);
  });

  it('starts from an empty list without inventing a folder', () => {
    expect(addRecentFolder([], 'D:\\a')).toEqual(['D:\\a']);
  });

  it('keeps at most MAX_RECENT_FOLDERS entries', () => {
    const full = Array.from({ length: MAX_RECENT_FOLDERS }, (_, i) => `D:\\p${i}`);

    const next = addRecentFolder(full, 'D:\\new');

    expect(next).toHaveLength(MAX_RECENT_FOLDERS);
    expect(next[0]).toBe('D:\\new');
  });
});

describe('migrateWorkspacePreferences', () => {
  it('clears the hardcoded path and its recent entry', () => {
    expect(
      migrateWorkspacePreferences({ currentWorkspacePath: LEGACY_PATH, recentProjects: [LEGACY_PATH, 'D:\\mine'] }),
    ).toEqual({ currentWorkspacePath: '', recentProjects: ['D:\\mine'] });
  });

  it('keeps folders the user picked', () => {
    expect(
      migrateWorkspacePreferences({ currentWorkspacePath: 'D:\\mine', recentProjects: ['D:\\mine'] }),
    ).toEqual({ currentWorkspacePath: 'D:\\mine', recentProjects: ['D:\\mine'] });
  });

  it('starts empty when nothing was stored', () => {
    expect(migrateWorkspacePreferences({})).toEqual({ currentWorkspacePath: '', recentProjects: [] });
  });

  it('drops malformed stored values instead of keeping them', () => {
    expect(migrateWorkspacePreferences({ currentWorkspacePath: 42, recentProjects: 'D:\\a' })).toEqual({
      currentWorkspacePath: '',
      recentProjects: [],
    });
  });
});
