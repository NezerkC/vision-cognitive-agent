import React, { Suspense } from 'react';
import { Panel, Group } from "react-resizable-panels";
import { useSettingsStore } from './stores/useSettingsStore';
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

  return (
    <div className="app">
      <TitleBar />
      <MenuBar />

      <div className="main">
        <ActivityBar />

        <Group orientation="horizontal" className="flex-1 overflow-hidden" autoSaveId="vision-layout">
          {/* Panel Izquierdo: Explorador */}
          <Panel defaultSize={15} minSize={10}>
            <Suspense fallback={<div className="h-full w-full bg-[#252526]"></div>}>
              <SidebarComponents />
            </Suspense>
          </Panel>

          {/* Panel Central: Editor y Terminal */}
          <Panel defaultSize={65} minSize={30}>
            <div className="editor-area">
              <Group orientation="vertical" autoSaveId="vision-editor-layout">
                <Panel defaultSize={isTerminalOpen ? 70 : 100} minSize={20}>
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
                  <Panel defaultSize={30} minSize={10} className="terminal-panel">
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
          <Panel defaultSize={20} minSize={15}>
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
