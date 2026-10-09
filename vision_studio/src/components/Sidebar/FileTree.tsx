import { useCallback, useEffect, useReducer, useRef } from 'react';
import type { ReactNode } from 'react';
import { Folder, FolderOpen, FileText, ChevronRight, ChevronDown, RefreshCw, FileCode, FileJson, FileType } from 'lucide-react';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';
import {
  DirEntry,
  ROOT_DIR,
  TreeState,
  emptyTree,
  fileTreeReducer,
  listDir,
  needsLoad,
  truncationNotice,
  workspaceName,
} from '../../lib/fileTree';

interface TreeProps {
  tree: TreeState;
  load: (path: string) => void;
  toggle: (path: string) => void;
}

function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase();
  if (ext === 'py') return <FileCode size={14} className="text-emerald-400" />;
  if (ext === 'ts' || ext === 'tsx' || ext === 'js' || ext === 'jsx') return <FileCode size={14} className="text-blue-400" />;
  if (ext === 'json') return <FileJson size={14} className="text-yellow-400" />;
  if (ext === 'md' || ext === 'txt') return <FileType size={14} className="text-purple-400" />;
  return <FileText size={14} className="text-gray-400" />;
}

/** A status line inside the tree: centered at the top level, indented under a folder. */
function Note({ level, tone, children }: { level: number; tone: 'muted' | 'error' | 'warning'; children: ReactNode }) {
  const color = tone === 'error' ? 'text-red-400' : tone === 'warning' ? 'text-amber-400' : 'text-gray-500 italic';
  if (level === 0) return <div className={`text-[11px] p-3 text-center break-words ${color}`}>{children}</div>;
  return (
    <div className={`text-[11px] py-1 pr-2 break-words ${color}`} style={{ paddingLeft: `${level * 12 + 18}px` }}>
      {children}
    </div>
  );
}

/** A folder's entries, listed through Rust the first time they are shown, or the error or cap notice it returned. */
function FolderContents({ path, level, tree, load, toggle }: TreeProps & { path: string; level: number }) {
  const dir = tree.dirs[path];
  useEffect(() => {
    if (needsLoad(dir)) load(path);
  }, [dir, path, load]);

  if (dir?.status === 'error') return <Note level={level} tone="error">{dir.error}</Note>;
  const listing = dir ? dir.listing : null;
  if (!listing) return <Note level={level} tone="muted">Cargando…</Note>;
  if (listing.entries.length === 0) {
    return <Note level={level} tone="muted">{level === 0 ? 'Carpeta vacía o sin archivos visibles.' : 'Carpeta vacía.'}</Note>;
  }
  const notice = truncationNotice(listing);
  return (
    <>
      {listing.entries.map((entry) => (
        <TreeEntry key={entry.path} entry={entry} level={level} tree={tree} load={load} toggle={toggle} />
      ))}
      {notice && <Note level={level} tone="warning">{notice}</Note>}
    </>
  );
}

function TreeEntry({ entry, level, tree, load, toggle }: TreeProps & { entry: DirEntry; level: number }) {
  if (entry.is_dir) {
    const isOpen = Boolean(tree.expanded[entry.path]);
    return (
      <div className="flex flex-col">
        <div
          onClick={() => toggle(entry.path)}
          className="flex items-center gap-1 cursor-pointer hover:bg-[#2a2d2e] py-1 px-1 rounded transition-colors text-xs text-gray-300 hover:text-white"
          style={{ paddingLeft: `${level * 12 + 4}px` }}
          title={entry.path}
        >
          {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {isOpen ? <FolderOpen size={14} className="text-blue-400 flex-shrink-0" /> : <Folder size={14} className="text-blue-400 flex-shrink-0" />}
          <span className="font-medium truncate ml-1">{entry.name}</span>
        </div>

        {isOpen && <FolderContents path={entry.path} level={level + 1} tree={tree} load={load} toggle={toggle} />}
      </div>
    );
  }

  return (
    <div
      className="flex items-center gap-1.5 cursor-pointer hover:bg-[#2a2d2e] py-1 px-1 rounded transition-colors text-xs text-gray-300 hover:text-white"
      style={{ paddingLeft: `${level * 12 + 18}px` }}
      title={entry.path}
    >
      {fileIcon(entry.name)}
      <span className="truncate">{entry.name}</span>
    </div>
  );
}

function Header({ name, loading, onRefresh }: { name: string; loading?: boolean; onRefresh?: () => void }) {
  return (
    <div className="flex items-center justify-between p-1.5 border-b border-[#3c3c3c]/50 mb-1">
      <span className="font-semibold uppercase tracking-wider text-[10px] text-gray-300 flex items-center gap-1">
        <FolderOpen size={12} className="text-blue-400" /> {name}
      </span>
      {onRefresh && (
        <button
          onClick={onRefresh}
          className="p-1 hover:bg-[#3c3c3c] rounded text-gray-400 hover:text-white transition-colors"
          title="Actualizar Archivos"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin text-[#0e639c]' : ''} />
        </button>
      )}
    </div>
  );
}

/** The tree of one workspace root. Folders are listed one level at a time, when expanded, by the Rust `list_dir`. */
function WorkspaceTree({ root }: { root: string }) {
  const [tree, dispatch] = useReducer(fileTreeReducer, emptyTree);
  const lastRequest = useRef(0);

  const load = useCallback((path: string) => {
    const request = ++lastRequest.current;
    dispatch({ type: 'loadStarted', path, request });
    listDir(path).then(
      (listing) => dispatch({ type: 'loadSucceeded', path, request, listing }),
      (err) => dispatch({ type: 'loadFailed', path, request, error: String(err) }),
    );
  }, []);
  const toggle = useCallback((path: string) => dispatch({ type: 'toggled', path }), []);
  const loading = Object.values(tree.dirs).some((dir) => dir.status === 'loading');

  return (
    <div className="flex flex-col text-xs text-gray-400 select-none p-1">
      <Header name={workspaceName(root)} loading={loading} onRefresh={() => dispatch({ type: 'refreshed' })} />
      <div className="space-y-0.5 overflow-y-auto custom-scrollbar">
        <FolderContents path={ROOT_DIR} level={0} tree={tree} load={load} toggle={toggle} />
      </div>
    </div>
  );
}

export default function FileTree() {
  const root = useWorkspaceStore((state) => state.root);
  const openError = useWorkspaceStore((state) => state.error);

  if (root === null) {
    return (
      <div className="flex flex-col text-xs text-gray-400 select-none p-1">
        <Header name="Workspace" />
        <Note level={0} tone={openError ? 'error' : 'muted'}>{openError ?? 'Abriendo proyecto…'}</Note>
      </div>
    );
  }
  // A new root starts a fresh tree, so listings of the previous workspace (even replies still on their way) are dropped.
  return <WorkspaceTree key={root} root={root} />;
}
