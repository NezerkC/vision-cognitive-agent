import React, { useEffect } from 'react';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { Files, Search, GitBranch, Blocks, MessageSquare, Settings, BookOpen, Kanban } from 'lucide-react';

export default function ActivityBar() {
  const setSettingsOpen = useSettingsStore((state) => state.setSettingsModalOpen);
  const activeTab = useSettingsStore((state) => state.activeSidebarTab);
  const setActiveTab = useSettingsStore((state) => state.setActiveSidebarTab);
  const isSidebarVisible = useSettingsStore((state) => state.isSidebarVisible);
  const toggleSidebar = useSettingsStore((state) => state.toggleSidebar);
  const setSidebarVisible = useSettingsStore((state) => state.setSidebarVisible);

  const handleTabClick = (tab: string) => {
    if (activeTab === tab && isSidebarVisible) {
      toggleSidebar();
    } else {
      setActiveTab(tab);
      setSidebarVisible(true);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleSidebar]);

  return (
    <div className="activitybar select-none">
      <button 
        className={`act-btn ${activeTab === 'explorer' && isSidebarVisible ? 'active' : ''}`} 
        onClick={() => handleTabClick('explorer')}
        title="Explorador (Ctrl+B)"
      >
        <Files size={22} strokeWidth={1.5} />
      </button>
      <button 
        className={`act-btn ${activeTab === 'notebooks' && isSidebarVisible ? 'active' : ''}`} 
        onClick={() => handleTabClick('notebooks')}
        title="Cuadernos (NotebookLM)"
      >
        <BookOpen size={22} strokeWidth={1.5} />
      </button>
      <button 
        className={`act-btn ${activeTab === 'agents' && isSidebarVisible ? 'active' : ''}`} 
        onClick={() => handleTabClick('agents')}
        title="Plan de Agentes (Kanban)"
      >
        <Kanban size={22} strokeWidth={1.5} />
      </button>
      <button 
        className={`act-btn ${activeTab === 'search' && isSidebarVisible ? 'active' : ''}`} 
        onClick={() => handleTabClick('search')}
        title="Buscar"
      >
        <Search size={22} strokeWidth={1.5} />
      </button>
      <button 
        className={`act-btn ${activeTab === 'git' && isSidebarVisible ? 'active' : ''}`} 
        onClick={() => handleTabClick('git')}
        title="Control de versiones"
      >
        <GitBranch size={22} strokeWidth={1.5} />
      </button>
      <button 
        className={`act-btn ${activeTab === 'extensions' && isSidebarVisible ? 'active' : ''}`} 
        onClick={() => handleTabClick('extensions')}
        title="Extensiones"
      >
        <Blocks size={22} strokeWidth={1.5} />
      </button>
      <div className="spacer"></div>
      <button 
        className={`act-btn ai-btn ${activeTab === 'chat' && isSidebarVisible ? 'active' : ''}`} 
        onClick={() => handleTabClick('chat')}
        title="Chat con IA (Ctrl+L)"
      >
        <MessageSquare size={22} strokeWidth={1.5} />
      </button>
      <button className="act-btn" onClick={() => setSettingsOpen(true)} title="Configuración">
        <Settings size={22} strokeWidth={1.5} />
      </button>
    </div>
  );
}
