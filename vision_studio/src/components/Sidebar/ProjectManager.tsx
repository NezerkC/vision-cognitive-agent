import { useState } from 'react';
import { FolderOpen, GitPullRequest, History, ArrowRight, Loader2, Folder, CheckCircle, AlertCircle } from 'lucide-react';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { pickWorkspaceFolder } from '../../lib/workspaceDialog';

interface ProjectManagerProps {
  onWorkspaceOpened?: (path: string) => void;
}

export default function ProjectManager({ onWorkspaceOpened }: ProjectManagerProps) {
  const currentWorkspacePath = useSettingsStore(state => state.currentWorkspacePath);
  const setCurrentWorkspacePath = useSettingsStore(state => state.setCurrentWorkspacePath);
  const recentProjects = useSettingsStore(state => state.recentProjects);
  const addRecentProject = useSettingsStore(state => state.addRecentProject);

  const [isPicking, setIsPicking] = useState(false);

  const [gitUrl, setGitUrl] = useState('');
  const [showGitModal, setShowGitModal] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleOpenFolder = (path: string) => {
    if (!path.trim()) return;
    const cleanPath = path.trim();
    setCurrentWorkspacePath(cleanPath);
    addRecentProject(cleanPath);
    if (onWorkspaceOpened) onWorkspaceOpened(cleanPath);
  };

  const handlePickFolder = async () => {
    if (isPicking) return;
    setIsPicking(true);
    setStatusMessage(null);
    try {
      const path = await pickWorkspaceFolder();
      if (path) handleOpenFolder(path);
    } catch (err) {
      setStatusMessage({ type: 'error', text: `No se pudo abrir el selector de carpetas: ${String(err)}` });
    } finally {
      setIsPicking(false);
    }
  };

  const handleCloneGit = async () => {
    if (!gitUrl.trim() || isCloning) return;
    setIsCloning(true);
    setStatusMessage(null);

    try {
      const res = await fetch('http://127.0.0.1:8000/api/workspace/clone_git', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: gitUrl })
      });
      const data = await res.json();
      if (data.status === 'success') {
        const clonedPath = data.workspace_path;
        setCurrentWorkspacePath(clonedPath);
        addRecentProject(clonedPath);
        setStatusMessage({ type: 'success', text: `Repositorio clonado exitosamente en ${data.workspace_name}` });
        setGitUrl('');
        setShowGitModal(false);
        if (onWorkspaceOpened) onWorkspaceOpened(clonedPath);
      } else {
        setStatusMessage({ type: 'error', text: data.message || 'Error al clonar el repositorio.' });
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: `Error de conexión: ${err.message}` });
    } finally {
      setIsCloning(false);
    }
  };

  return (
    <div className="p-3 space-y-4 text-xs font-sans select-none">
      {/* Botones Principales de Gestor de Proyectos */}
      <div className="space-y-2">
        <button
          onClick={handlePickFolder}
          disabled={isPicking}
          className="w-full bg-[#0e639c] hover:bg-[#1177bb] disabled:opacity-50 text-white p-2 rounded flex items-center justify-center gap-2 font-medium transition-colors"
        >
          <FolderOpen size={14} /> {isPicking ? 'Esperando la carpeta…' : 'Abrir Carpeta'}
        </button>

        <button
          onClick={() => setShowGitModal(prev => !prev)}
          className="w-full bg-[#252526] hover:bg-[#2a2d2e] border border-[#3c3c3c] text-white p-2 rounded flex items-center justify-center gap-2 font-medium transition-colors"
        >
          <GitPullRequest size={14} className="text-amber-400" /> Clonar Repositorio Git
        </button>
      </div>

      {/* Formulario Clonar Git */}
      {showGitModal && (
        <div className="bg-[#1e1e1f] p-2.5 rounded border border-[#3c3c3c] space-y-2 animate-fadeIn">
          <span className="text-[11px] font-semibold text-amber-400 block">URL del Repositorio de Git:</span>
          <input 
            type="text" 
            placeholder="https://github.com/usuario/repositorio.git" 
            value={gitUrl}
            onChange={e => setGitUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCloneGit()}
            disabled={isCloning}
            className="w-full bg-[#2d2d2d] border border-[#3c3c3c] rounded px-2 py-1 text-xs text-white outline-none focus:border-amber-400"
          />
          <div className="flex justify-end gap-1">
            <button onClick={() => setShowGitModal(false)} disabled={isCloning} className="px-2 py-0.5 text-gray-400 hover:text-white text-[10px]">Cancelar</button>
            <button 
              onClick={handleCloneGit} 
              disabled={isCloning || !gitUrl.trim()}
              className="px-2 py-0.5 bg-amber-500 hover:bg-amber-600 text-black font-semibold rounded text-[10px] flex items-center gap-1 disabled:opacity-50"
            >
              {isCloning ? <Loader2 size={10} className="animate-spin" /> : <ArrowRight size={10} />} Clonar
            </button>
          </div>
        </div>
      )}

      {/* Mensaje de Estado */}
      {statusMessage && (
        <div className={`p-2 rounded border text-[11px] flex items-center gap-1.5 ${
          statusMessage.type === 'success' ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30' : 'bg-red-500/10 text-red-300 border-red-500/30'
        }`}>
          {statusMessage.type === 'success' ? <CheckCircle size={12} /> : <AlertCircle size={12} />}
          <span>{statusMessage.text}</span>
        </div>
      )}

      {/* Lista de Proyectos Recientes */}
      <div className="space-y-1.5 pt-2 border-t border-[#3c3c3c]">
        <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1">
          <History size={12} /> Proyectos Recientes
        </span>

        {recentProjects.length === 0 ? (
          <span className="text-[11px] text-gray-500 italic block p-2">No hay proyectos recientes.</span>
        ) : (
          recentProjects.map((p, idx) => {
            const folderName = p.split(/[/\\]/).pop() || p;
            const isCurrent = p === currentWorkspacePath;
            return (
              <div 
                key={idx}
                onClick={() => handleOpenFolder(p)}
                className={`p-2 rounded cursor-pointer transition-colors flex items-center justify-between group ${
                  isCurrent ? 'bg-[#37373d] text-white border-l-2 border-[#0e639c]' : 'hover:bg-[#2a2d2e] text-gray-300'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0 pr-2">
                  <Folder size={14} className={isCurrent ? 'text-[#0e639c]' : 'text-gray-400'} />
                  <div className="flex flex-col min-w-0">
                    <span className="font-medium truncate">{folderName}</span>
                    <span className="text-[9px] text-gray-500 truncate">{p}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
