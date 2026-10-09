import React, { Suspense, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Panel, Group, useDefaultLayout } from "react-resizable-panels";
import { useSettingsStore } from './stores/useSettingsStore';
import { useNotificationStore } from './stores/useNotificationStore';
import { useWorkspaceStore } from './stores/useWorkspaceStore';
import SettingsModal from './components/Settings/SettingsModal';
import ToastContainer from './components/Notifications/ToastContainer';
import TitleBar from './components/Layout/TitleBar';
import ActivityBar from './components/Layout/ActivityBar';
import StatusBar from './components/Layout/StatusBar';
import MenuBar from './components/Layout/MenuBar';

// Carga diferida de componentes
const SidebarComponents = React.lazy(() => import('./components/Sidebar/SidebarComponents'));
const CognitiveEditor = React.lazy(() => import('./components/Editor/CognitiveEditor'));
const IntegratedTerminal = React.lazy(() => import('./components/Terminal/IntegratedTerminal'));
const Radar3D = React.lazy(() => import('./components/Memory/Radar3D'));
const AgentsSynapticView = React.lazy(() => import('./components/Agents/AgentsSynapticView'));

export default function App() {
  const isSettingsOpen = useSettingsStore((state) => state.isSettingsModalOpen);
  const setSettingsOpen = useSettingsStore((state) => state.setSettingsModalOpen);
  const isTerminalOpen = useSettingsStore((state) => state.isTerminalOpen);
  const activeSidebarTab = useSettingsStore((state) => state.activeSidebarTab);
  const currentWorkspacePath = useSettingsStore((state) => state.currentWorkspacePath);
  const addToast = useNotificationStore((state) => state.addToast);
  const workspaceOpened = useWorkspaceStore((state) => state.opened);
  const workspaceFailed = useWorkspaceStore((state) => state.failed);

  // The Rust file and shell commands only act inside the workspace registered here. The explorer waits for the root
  // Rust confirms, so it never lists before Rust switched to the new folder; replies for a replaced path are ignored.
  // With no folder chosen yet there is nothing to register: the explorer shows its empty state instead.
  useEffect(() => {
    if (!currentWorkspacePath) return;
    let current = true;
    invoke<string>('set_workspace', { path: currentWorkspacePath })
      .then((root) => {
        if (current) workspaceOpened(root);
      })
      .catch((err) => {
        if (!current) return;
        workspaceFailed(String(err));
        addToast({ title: 'Proyecto no disponible', message: String(err), type: 'error' });
      });
    return () => {
      current = false;
    };
  }, [currentWorkspacePath, addToast, workspaceOpened, workspaceFailed]);

  // Persist panel layouts across reloads (localStorage); replaces the pre-v4 autoSaveId prop.
  const mainLayout = useDefaultLayout({ id: 'vision-layout' });
  // panelIds keeps a separate saved layout per terminal open/closed combination.
  const editorLayout = useDefaultLayout({
    id: 'vision-editor-layout',
    panelIds: isTerminalOpen ? ['editor-main-panel', 'terminal-panel'] : ['editor-main-panel'],
  });

  return (
    <div className="app">
      <TitleBar />
      <MenuBar />

      <div className="main">
        <ActivityBar />

        <Group orientation="horizontal" className="flex-1 overflow-hidden" defaultLayout={mainLayout.defaultLayout} onLayoutChanged={mainLayout.onLayoutChanged}>
          {/* Panel Izquierdo: Explorador */}
          <Panel id="sidebar-panel" defaultSize="15%" minSize="10%">
            <Suspense fallback={<div className="h-full w-full bg-[#252526]"></div>}>
              <SidebarComponents />
            </Suspense>
          </Panel>

          {/* Panel Central: Editor y Terminal */}
          <Panel id="editor-panel" defaultSize="65%" minSize="30%">
            <div className="editor-area">
              <Group orientation="vertical" defaultLayout={editorLayout.defaultLayout} onLayoutChanged={editorLayout.onLayoutChanged}>
                <Panel id="editor-main-panel" defaultSize={isTerminalOpen ? "70%" : "100%"} minSize="20%">
                  {activeSidebarTab === 'agents' ? (
                    <Suspense fallback={<div className="editor-placeholder">Cargando Mapa Cerebral Sináptico...</div>}>
                      <AgentsSynapticView />
                    </Suspense>
                  ) : (
                    <Suspense fallback={<div className="editor-placeholder">Cargando Editor...</div>}>
                      <CognitiveEditor />
                    </Suspense>
                  )}
                </Panel>
                
                {isTerminalOpen && (
                  <Panel id="terminal-panel" defaultSize="30%" minSize="10%" className="terminal-panel">
                    <div className="terminal-header">
                      <span>TERMINAL — bash</span>
                      <span className="close-term" onClick={() => useSettingsStore.getState().setTerminalOpen(false)}>✕</span>
                    </div>
                    <Suspense fallback={<div className="terminal-output">Iniciando terminal...</div>}>
                      <IntegratedTerminal />
                    </Suspense>
                  </Panel>
                )}
              </Group>
            </div>
          </Panel>

          {/* Panel Derecho: Chat & Radar */}
          <Panel id="chat-panel" defaultSize="20%" minSize="15%">
            <div className="chat-panel">
              <div className="chat-header">
                <div className="title">Memoria y Contexto (Radar 4D)</div>
              </div>
              <div className="flex-1 relative bg-black/50">
                <Suspense fallback={<div className="h-full flex items-center justify-center text-gray-500">Iniciando Radar...</div>}>
                  <Radar3D />
                </Suspense>
              </div>
            </div>
          </Panel>
        </Group>
      </div>

      <StatusBar />
      
      <SettingsModal 
        isOpen={isSettingsOpen} 
        onClose={() => setSettingsOpen(false)} 
      />

      <ToastContainer />
    </div>
  );
}
