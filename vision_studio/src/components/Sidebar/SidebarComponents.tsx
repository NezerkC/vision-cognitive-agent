import React from 'react';
import FileTree from './FileTree';
import ProjectManager from './ProjectManager';
import SidebarChat from './SidebarChat';
import NotebooksView from '../Notebooks/NotebooksView';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { Search, ChevronRight, Check, X } from 'lucide-react';

export default function SidebarComponents() {
  const activeTab = useSettingsStore((state) => state.activeSidebarTab);
  const isSidebarVisible = useSettingsStore((state) => state.isSidebarVisible);
  const setSidebarVisible = useSettingsStore((state) => state.setSidebarVisible);

  if (!isSidebarVisible) return null;

  const getTitle = () => {
    switch (activeTab) {
      case 'explorer': return 'EXPLORADOR';
      case 'notebooks': return 'CUADERNOS';
      case 'search': return 'BUSCAR';
      case 'git': return 'CONTROL DE VERSIONES';
      case 'extensions': return 'EXTENSIONES';
      case 'agents': return 'PLAN DE AGENTES';
      case 'chat': return 'CHAT CON IA';
      default: return 'EXPLORADOR';
    }
  };

  return (
    <div className="sidebar select-none">
      <div className="sidebar-header text-[#cccccc] font-semibold tracking-wide text-xs px-3 py-2 uppercase flex items-center justify-between border-b border-[#3c3c3c]">
        <span>{getTitle()}</span>
        <button 
          onClick={() => setSidebarVisible(false)}
          className="p-1 hover:bg-[#3c3c3c] rounded text-gray-400 hover:text-white transition-colors"
          title="Cerrar Barra Lateral (Ctrl+B)"
        >
          <X size={14} />
        </button>
      </div>
      
      <div className="sidebar-project no-scrollbar flex-1 overflow-y-auto relative flex flex-col">
        {activeTab === 'explorer' && (
          <div className="flex flex-col h-full space-y-2">
            <ProjectManager />
            <div className="border-t border-[#3c3c3c] pt-1 flex-1 overflow-y-auto">
              <FileTree />
            </div>
          </div>
        )}
        
        {activeTab === 'search' && (
          <div className="p-4 space-y-4">
            <div className="relative">
              <input type="text" placeholder="Buscar en archivos..." className="w-full bg-[#3c3c3c] border border-transparent focus:border-[#a78bfa] rounded text-[#cccccc] text-xs px-2 py-1.5 pl-6 outline-none" />
              <Search size={14} className="absolute left-1.5 top-2 text-[#8a8a8a]" />
            </div>
            <div className="relative">
              <input type="text" placeholder="Reemplazar..." className="w-full bg-[#3c3c3c] border border-transparent focus:border-[#a78bfa] rounded text-[#cccccc] text-xs px-2 py-1.5 outline-none" />
            </div>
          </div>
        )}
        
        {activeTab === 'git' && (
          <div className="p-4 space-y-4">
            <div className="text-xs text-[#8a8a8a] flex items-center gap-1">
              <ChevronRight size={14}/> Cambios (3)
            </div>
            <div className="space-y-1">
              <div className="text-xs text-[#cccccc] flex items-center justify-between hover:bg-[#2a2d2e] p-1 cursor-pointer">
                <span>src/App.tsx</span> <span className="text-[#e2c08d]">M</span>
              </div>
              <div className="text-xs text-[#cccccc] flex items-center justify-between hover:bg-[#2a2d2e] p-1 cursor-pointer">
                <span>src/index.css</span> <span className="text-[#e2c08d]">M</span>
              </div>
              <div className="text-xs text-[#cccccc] flex items-center justify-between hover:bg-[#2a2d2e] p-1 cursor-pointer">
                <span>src/stores/useSettingsStore.ts</span> <span className="text-[#73c991]">U</span>
              </div>
            </div>
            <textarea placeholder="Mensaje de confirmación (Ctrl+Enter)" className="w-full bg-[#3c3c3c] border border-transparent focus:border-[#a78bfa] rounded text-[#cccccc] text-xs p-2 outline-none resize-none h-20" />
            <button className="w-full bg-[#0e639c] hover:bg-[#1177bb] text-white text-xs rounded py-1.5 flex items-center justify-center gap-1">
              <Check size={14}/> Confirmar (Commit)
            </button>
          </div>
        )}
        
        {activeTab === 'extensions' && (
          <div className="p-4 space-y-4">
            <input type="text" placeholder="Buscar extensiones de IA..." className="w-full bg-[#3c3c3c] border border-transparent focus:border-[#a78bfa] rounded text-[#cccccc] text-xs px-2 py-1.5 outline-none" />
            <div className="space-y-2">
              <div className="flex items-start gap-2 p-2 hover:bg-[#2a2d2e] rounded cursor-pointer">
                <div className="w-8 h-8 bg-blue-500 rounded flex-shrink-0" />
                <div className="flex flex-col">
                  <span className="text-[#cccccc] text-xs font-semibold">Prettier - Code formatter</span>
                  <span className="text-[#8a8a8a] text-[10px]">Esben Petersen</span>
                </div>
              </div>
              <div className="flex items-start gap-2 p-2 hover:bg-[#2a2d2e] rounded cursor-pointer">
                <div className="w-8 h-8 bg-purple-500 rounded flex-shrink-0" />
                <div className="flex flex-col">
                  <span className="text-[#cccccc] text-xs font-semibold">ESLint</span>
                  <span className="text-[#8a8a8a] text-[10px]">Microsoft</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'agents' && (
          <div className="p-4 space-y-4 text-xs text-[#cccccc]">
            <div className="bg-purple-950/40 border border-purple-800/40 rounded p-3 space-y-2">
              <h3 className="font-semibold text-purple-300 flex items-center gap-1.5">
                🧠 Orquestación Cognitiva
              </h3>
              <p className="text-[11px] text-gray-400 leading-relaxed">
                Visualización de **Agentes Entrelazadores**. Gestiona la asignación de tareas a los lóbulos (Frontal, Parietal, Hemisferio Izquierdo y Sentidos).
              </p>
            </div>

            <div className="space-y-2">
              <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Lóbulos Activos</div>
              <div className="space-y-1.5">
                <div className="p-2 bg-[#252526] border border-[#3c3c3c] rounded flex items-center justify-between">
                  <span className="text-purple-300">🧠 Lóbulo Frontal</span>
                  <span className="bg-purple-900/60 text-purple-200 text-[10px] px-1.5 py-0.5 rounded">Decisión</span>
                </div>
                <div className="p-2 bg-[#252526] border border-[#3c3c3c] rounded flex items-center justify-between">
                  <span className="text-cyan-300">📚 Lóbulo Parietal</span>
                  <span className="bg-cyan-900/60 text-cyan-200 text-[10px] px-1.5 py-0.5 rounded">Memoria/RAG</span>
                </div>
                <div className="p-2 bg-[#252526] border border-[#3c3c3c] rounded flex items-center justify-between">
                  <span className="text-emerald-300">💻 Hemisferio Izq.</span>
                  <span className="bg-emerald-900/60 text-emerald-200 text-[10px] px-1.5 py-0.5 rounded">Terminal CLI</span>
                </div>
                <div className="p-2 bg-[#252526] border border-[#3c3c3c] rounded flex items-center justify-between">
                  <span className="text-amber-300">🌐 Sentidos</span>
                  <span className="bg-amber-900/60 text-amber-200 text-[10px] px-1.5 py-0.5 rounded">Web Search</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'notebooks' && (
          <div className="absolute inset-0 max-w-full overflow-hidden">
            <NotebooksView />
          </div>
        )}

        {activeTab === 'chat' && (
          <div className="absolute inset-0 max-w-full overflow-hidden">
            <SidebarChat />
          </div>
        )}
      </div>
    </div>
  );
}
