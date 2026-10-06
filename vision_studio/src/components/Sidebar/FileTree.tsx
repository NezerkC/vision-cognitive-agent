import { useState, useEffect } from 'react';
import { Folder, FolderOpen, FileText, ChevronRight, ChevronDown, RefreshCw, FileCode, FileJson, FileType } from 'lucide-react';
import { useSettingsStore } from '../../stores/useSettingsStore';

interface FileNode {
  name: string;
  path: string;
  is_dir: boolean;
  children?: FileNode[];
}

function FileTreeNode({ node, level = 0 }: { node: FileNode; level?: number }) {
  const [isOpen, setIsOpen] = useState(level === 0);

  const getFileIcon = (name: string) => {
    const ext = name.split('.').pop()?.toLowerCase();
    if (ext === 'py') return <FileCode size={14} className="text-emerald-400" />;
    if (ext === 'ts' || ext === 'tsx' || ext === 'js' || ext === 'jsx') return <FileCode size={14} className="text-blue-400" />;
    if (ext === 'json') return <FileJson size={14} className="text-yellow-400" />;
    if (ext === 'md' || ext === 'txt') return <FileType size={14} className="text-purple-400" />;
    return <FileText size={14} className="text-gray-400" />;
  };

  if (node.is_dir) {
    return (
      <div className="flex flex-col">
        <div 
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-1 cursor-pointer hover:bg-[#2a2d2e] py-1 px-1 rounded transition-colors text-xs text-gray-300 hover:text-white"
          style={{ paddingLeft: `${level * 12 + 4}px` }}
        >
          {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {isOpen ? <FolderOpen size={14} className="text-blue-400 flex-shrink-0" /> : <Folder size={14} className="text-blue-400 flex-shrink-0" />}
          <span className="font-medium truncate ml-1">{node.name}</span>
        </div>

        {isOpen && node.children && (
          <div className="flex flex-col">
            {node.children.map((child, idx) => (
              <FileTreeNode key={idx} node={child} level={level + 1} />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div 
      className="flex items-center gap-1.5 cursor-pointer hover:bg-[#2a2d2e] py-1 px-1 rounded transition-colors text-xs text-gray-300 hover:text-white"
      style={{ paddingLeft: `${level * 12 + 18}px` }}
    >
      {getFileIcon(node.name)}
      <span className="truncate">{node.name}</span>
    </div>
  );
}

export default function FileTree() {
  const currentWorkspacePath = useSettingsStore(state => state.currentWorkspacePath);
  const [treeData, setTreeData] = useState<FileNode[]>([]);
  const [workspaceName, setWorkspaceName] = useState('Workspace');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Opening the folder makes it the gateway's active workspace; the tree and file search stay inside it.
  const fetchWorkspaceTree = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/workspace/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: currentWorkspacePath }),
      });
      const data = await res.json();
      if (!res.ok) {
        setTreeData([]);
        setError(data.detail ?? `Error ${res.status} al abrir la carpeta.`);
        return;
      }
      setTreeData(data.tree);
      setWorkspaceName(data.workspace_name);
    } catch (err) {
      setTreeData([]);
      setError('No se pudo conectar con el gateway en 127.0.0.1:8000.');
      console.error('Error loading workspace tree:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkspaceTree();
  }, [currentWorkspacePath]);

  return (
    <div className="flex flex-col text-xs text-gray-400 select-none p-1">
      {/* Workspace Header */}
      <div className="flex items-center justify-between p-1.5 border-b border-[#3c3c3c]/50 mb-1">
        <span className="font-semibold uppercase tracking-wider text-[10px] text-gray-300 flex items-center gap-1">
          <FolderOpen size={12} className="text-blue-400" /> {workspaceName}
        </span>
        <button 
          onClick={fetchWorkspaceTree} 
          className="p-1 hover:bg-[#3c3c3c] rounded text-gray-400 hover:text-white transition-colors"
          title="Actualizar Archivos"
        >
          <RefreshCw size={12} className={isLoading ? 'animate-spin text-[#0e639c]' : ''} />
        </button>
      </div>

      {/* Tree Nodes */}
      <div className="space-y-0.5 overflow-y-auto custom-scrollbar">
        {error ? (
          <div className="text-[11px] text-red-400 p-3 text-center">{error}</div>
        ) : treeData.length === 0 && !isLoading ? (
          <div className="text-[11px] text-gray-500 italic p-3 text-center">
            Carpeta vacía o sin archivos visibles.
          </div>
        ) : (
          treeData.map((node, idx) => (
            <FileTreeNode key={idx} node={node} level={0} />
          ))
        )}
      </div>
    </div>
  );
}
