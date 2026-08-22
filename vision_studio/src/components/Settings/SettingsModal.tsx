import React, { useState } from 'react';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { Settings, Cpu, Mic, Volume2, X, Box, Network, Zap, Heart, Database, Check } from 'lucide-react';
import LlamaCppPanel from './LlamaCppPanel';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type SettingsTab = 'general' | 'modelos' | 'agentes' | 'mcp' | 'skills' | 'emociones';

const STATIC_MODELS: Record<string, {id: string, label: string}[]> = {
  ollama: ['llama3.2', 'llama3', 'mistral', 'phi3', 'qwen2', 'gemma', 'deepseek-coder-v2'].map(id => ({id, label: id})),
  openai: ['gpt-4o', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'].map(id => ({id, label: id})),
  anthropic: ['claude-3-5-sonnet-20240620', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'].map(id => ({id, label: id})),
  gemini: ['gemini-1.5-pro-latest', 'gemini-1.5-flash-latest', 'gemini-pro', 'gemini-pro-vision'].map(id => ({id, label: id})),
  groq: ['llama3-70b-8192', 'llama3-8b-8192', 'mixtral-8x7b-32768', 'gemma-7b-it'].map(id => ({id, label: id})),
  lmstudio: ['local-model'].map(id => ({id, label: id}))
};

const ProviderCard = ({ id, title, description, settings, models, requireApiKey = false, requireEndpoint = false }: any) => {
  const isActive = settings.provider === id;
  const activeModel = settings.providerModels?.[id] || '';

  return (
    <div className={`p-4 rounded-lg border transition-all ${isActive ? 'border-[#a78bfa] bg-[#2d2d35]' : 'border-[#3c3c3c] bg-[#252526] hover:border-[#5a5a5a]'}`}>
      <div className="flex items-center gap-3 mb-3 cursor-pointer" onClick={() => settings.setSetting('provider', id)}>
        <input type="radio" checked={isActive} readOnly className="accent-[#a78bfa]" />
        <div>
          <div className="font-medium text-white">{title}</div>
          <div className="text-[10px] text-[#8a8a8a]">{description}</div>
        </div>
      </div>
      
      <div className="space-y-2 mt-2">
        <input 
          type="text" 
          list={`list-${id}-${title.replace(/\s+/g, '')}`}
          value={activeModel}
          onChange={(e) => settings.setProviderModel(id, e.target.value)}
          placeholder="Escribe o selecciona modelo..."
          className="w-full bg-[#1e1e1e] border border-[#3c3c3c] text-[#cccccc] px-2 py-1.5 rounded outline-none focus:border-[#a78bfa] text-xs"
        />
        <datalist id={`list-${id}-${title.replace(/\s+/g, '')}`}>
          {models.map((m: any) => (
            <option key={m.id} value={m.id}>{m.label}</option>
          ))}
        </datalist>

        {requireApiKey && (
          <input 
            type="password" 
            value={settings.apiKeys[id] || ''}
            onChange={(e) => settings.setApiKey(id, e.target.value)}
            placeholder={`API Key`}
            className="w-full bg-[#1e1e1e] border border-[#3c3c3c] text-[#cccccc] px-2 py-1.5 rounded outline-none focus:border-[#a78bfa] text-xs mt-2"
          />
        )}

        {requireEndpoint && (
          <input 
            type="text" 
            value={settings.endpoints?.[id] || ''}
            onChange={(e) => settings.setEndpoint(id, e.target.value)}
            placeholder={`URL del Endpoint`}
            className="w-full bg-[#1e1e1e] border border-[#3c3c3c] text-[#cccccc] px-2 py-1.5 rounded outline-none focus:border-[#a78bfa] text-xs mt-2"
          />
        )}
      </div>
    </div>
  );
};

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const settings = useSettingsStore();
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [orModels, setOrModels] = useState<{id: string, label: string}[]>([]);
  const [isLoadingOr, setIsLoadingOr] = useState(false);

  // Obtener modelos de OpenRouter dinámicamente al abrir el modal o cargar
  React.useEffect(() => {
    let mounted = true;
    setIsLoadingOr(true);
    fetch('https://openrouter.ai/api/v1/models')
      .then(res => res.json())
      .then(data => {
        if (mounted && data && data.data) {
          const models = data.data.map((m: any) => {
            const isFree = m.pricing?.prompt === "0" && m.pricing?.completion === "0";
            return {
              id: m.id,
              label: isFree ? `${m.name} [FREE]` : m.name
            };
          });
          
          // Ordenar: Los FREE primero, luego alfabéticamente
          models.sort((a: any, b: any) => {
            const aFree = a.label.includes('[FREE]');
            const bFree = b.label.includes('[FREE]');
            if (aFree && !bFree) return -1;
            if (!aFree && bFree) return 1;
            return a.label.localeCompare(b.label);
          });
          
          setOrModels(models);
        }
      })
      .catch(err => console.error("Error fetching OR models", err))
      .finally(() => {
        if (mounted) setIsLoadingOr(false);
      });
      
    return () => { mounted = false; };
  }, []);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-[#1e1e1e] border border-[#3c3c3c] shadow-2xl rounded-lg w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden">
        
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b border-[#3c3c3c] bg-[#252526]">
          <div className="flex items-center gap-2 text-[#cccccc] font-medium tracking-wide">
            <Settings size={16} />
            <span>Configuración (Lóbulo Frontal)</span>
          </div>
          <button onClick={onClose} className="text-[#8a8a8a] hover:text-[#cccccc] transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar Tabs */}
          <div className="w-48 bg-[#252526] border-r border-[#3c3c3c] p-2 space-y-1 flex flex-col">
            <button 
              onClick={() => setActiveTab('general')}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-md w-full text-left transition-colors ${activeTab === 'general' ? 'bg-[#37373d] text-white' : 'bg-transparent text-[#cccccc] hover:bg-[#2a2d2e]'}`}
            >
              <Settings size={14} /> General
            </button>
            <button 
              onClick={() => setActiveTab('modelos')}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-md w-full text-left transition-colors ${activeTab === 'modelos' ? 'bg-[#37373d] text-white' : 'bg-transparent text-[#cccccc] hover:bg-[#2a2d2e]'}`}
            >
              <Database size={14} /> Modelos
            </button>
            <button 
              onClick={() => setActiveTab('agentes')}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-md w-full text-left transition-colors ${activeTab === 'agentes' ? 'bg-[#37373d] text-white' : 'bg-transparent text-[#cccccc] hover:bg-[#2a2d2e]'}`}
            >
              <Box size={14} /> Agentes
            </button>
            <button 
              onClick={() => setActiveTab('mcp')}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-md w-full text-left transition-colors ${activeTab === 'mcp' ? 'bg-[#37373d] text-white' : 'bg-transparent text-[#cccccc] hover:bg-[#2a2d2e]'}`}
            >
              <Network size={14} /> MCP
            </button>
            <button 
              onClick={() => setActiveTab('skills')}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-md w-full text-left transition-colors ${activeTab === 'skills' ? 'bg-[#37373d] text-white' : 'bg-transparent text-[#cccccc] hover:bg-[#2a2d2e]'}`}
            >
              <Zap size={14} /> Skills
            </button>
            <button 
              onClick={() => setActiveTab('emociones')}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-md w-full text-left transition-colors ${activeTab === 'emociones' ? 'bg-[#37373d] text-white' : 'bg-transparent text-[#cccccc] hover:bg-[#2a2d2e]'}`}
            >
              <Heart size={14} /> Emociones
            </button>
          </div>

          {/* Main Content Area */}
          <div className="flex-1 flex flex-col bg-[#1e1e1e]">
            <div className="flex-1 overflow-y-auto p-6 text-gray-300 custom-scrollbar space-y-8">
              
              {activeTab === 'general' && (
                <div className="space-y-6">
                  <h3 className="text-white text-lg border-b border-[#3c3c3c] pb-2">Configuración General</h3>
                  
                  {/* Estrategia Activa */}
                  <section className="space-y-3">
                    <label className="flex flex-col gap-1 text-xs">
                      <span className="font-semibold text-[#cccccc]">Estrategia de Ruta Activa</span>
                      <select 
                        value={settings.routingStrategy}
                        onChange={(e) => settings.setSetting('routingStrategy', e.target.value)}
                        className="bg-[#3c3c3c] border border-[#3c3c3c] text-[#cccccc] px-2 py-1.5 rounded outline-none w-max"
                      >
                        <option value="locales">💻 LOCALES (Offline / Ollama)</option>
                        <option value="hibrido_api">⚡ HÍBRIDO (API / Pay-Per-Call)</option>
                        <option value="suscripcion_mensual">💎 MENSUAL (ChatGPT Plus)</option>
                      </select>
                    </label>
                    
                    <label className="flex flex-col gap-1 text-xs">
                      <span className="font-semibold text-[#cccccc]">Nivel de Esfuerzo (LLM Router)</span>
                      <select 
                        value={settings.effortLevel}
                        onChange={(e) => settings.setSetting('effortLevel', e.target.value)}
                        className="bg-[#3c3c3c] border border-[#3c3c3c] text-[#cccccc] px-2 py-1.5 rounded outline-none w-max"
                      >
                        <option value="esfuerzo_bajo">🟢 Esfuerzo Bajo (Misión rápida, local/liviano)</option>
                        <option value="esfuerzo_medio">🟡 Esfuerzo Medio (Razonamiento / Coding intermedio)</option>
                        <option value="esfuerzo_alto">🔴 Esfuerzo Alto (Misiones complejas / Análisis profundo)</option>
                      </select>
                    </label>
                  </section>

                  {/* Hardware Sensorial */}
                  <section className="space-y-4 pt-4 border-t border-[#3c3c3c]">
                    <h4 className="text-[#cccccc] font-semibold flex items-center gap-2"><Mic size={16} /> Oído / STT</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <label className="flex flex-col gap-1 text-xs">
                        <span>Modo de Oído:</span>
                        <select 
                          value={settings.oidoMock.toString()}
                          onChange={(e) => settings.setSetting('oidoMock', e.target.value === 'true')}
                          className="bg-[#3c3c3c] border border-[#3c3c3c] text-[#cccccc] px-2 py-1.5 rounded outline-none"
                        >
                          <option value="false">🎤 Micrófono Físico Real</option>
                          <option value="true">🤖 Simulación / Mock Mode</option>
                        </select>
                      </label>
                      <label className="flex flex-col gap-1 text-xs">
                        <span>Modelo Whisper:</span>
                        <select 
                          value={settings.oidoWhisper}
                          onChange={(e) => settings.setSetting('oidoWhisper', e.target.value)}
                          className="bg-[#3c3c3c] border border-[#3c3c3c] text-[#cccccc] px-2 py-1.5 rounded outline-none"
                        >
                          <option value="tiny">Tiny (Rápido)</option>
                          <option value="base">Base (Balanceado)</option>
                          <option value="small">Small (Precisión)</option>
                        </select>
                      </label>
                    </div>
                  </section>

                  <section className="space-y-4 pt-4 border-t border-[#3c3c3c]">
                    <h4 className="text-[#cccccc] font-semibold flex items-center gap-2"><Volume2 size={16} /> Habla / TTS</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <label className="flex flex-col gap-1 text-xs">
                        <span>Modo de Habla:</span>
                        <select 
                          value={settings.hablaMock.toString()}
                          onChange={(e) => settings.setSetting('hablaMock', e.target.value === 'true')}
                          className="bg-[#3c3c3c] border border-[#3c3c3c] text-[#cccccc] px-2 py-1.5 rounded outline-none"
                        >
                          <option value="false">🔊 Altavoz Físico Real</option>
                          <option value="true">🤖 Simulación / Mock Mode</option>
                        </select>
                      </label>
                      <label className="flex flex-col gap-1 text-xs">
                        <span>Motor TTS:</span>
                        <select 
                          value={settings.hablaTts}
                          onChange={(e) => settings.setSetting('hablaTts', e.target.value)}
                          className="bg-[#3c3c3c] border border-[#3c3c3c] text-[#cccccc] px-2 py-1.5 rounded outline-none"
                        >
                          <option value="edge-tts">Edge TTS (Voz Natural Cloud)</option>
                          <option value="pyttsx3">PyTTSx3 (Offline / Local)</option>
                        </select>
                      </label>
                    </div>
                  </section>
                </div>
              )}

              {activeTab === 'modelos' && (
                <div className="space-y-8">
                  <div className="flex items-center justify-between border-b border-[#3c3c3c] pb-2">
                    <h3 className="text-white text-lg">Modelos de Lenguaje (LLMs)</h3>
                    {isLoadingOr && (
                      <span className="text-xs text-[#a78bfa] flex items-center gap-1 animate-pulse"><Zap size={14} /> Sincronizando OpenRouter...</span>
                    )}
                  </div>
                  
                  {/* Category: Locales / Gratis */}
                  <div className="space-y-4">
                    <h4 className="text-sm font-semibold text-[#8a8a8a] uppercase tracking-wider flex items-center gap-2">
                      <Cpu size={14} /> Locales / Gratis
                    </h4>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <ProviderCard 
                        id="ollama" title="Ollama" description="Local (Offline)"
                        settings={settings} models={STATIC_MODELS['ollama']}
                        requireEndpoint={true}
                      />
                      <ProviderCard 
                        id="llamacpp" title="Llama.cpp" description="Local (Server port 8080)"
                        settings={settings} models={[]}
                        requireEndpoint={true}
                      />
                      <ProviderCard 
                        id="lmstudio" title="LM Studio" description="Local (API local)"
                        settings={settings} models={STATIC_MODELS['lmstudio']}
                        requireEndpoint={true}
                      />
                      <ProviderCard 
                        id="openrouter" title="OpenRouter (Gratis)" description="API Cloud Gratuita"
                        settings={settings} models={orModels.filter(m => m.label.includes('[FREE]'))}
                        requireApiKey={true}
                      />
                    </div>
                  </div>

                  {/* Panel de Motor Local LM Studio / Llama.cpp */}
                  <div className="pt-4 border-t border-[#3c3c3c]">
                    <LlamaCppPanel />
                  </div>

                  {/* Category: Híbrido (APIs Pay-per-Call) */}
                  <div className="space-y-4 pt-4">
                    <h4 className="text-sm font-semibold text-[#8a8a8a] uppercase tracking-wider flex items-center gap-2">
                      <Network size={14} /> Híbrido (APIs Pay-per-Call)
                    </h4>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <ProviderCard 
                        id="openrouter" title="OpenRouter (Completo)" description="API Cloud (Todos los modelos)"
                        settings={settings} models={orModels}
                        requireApiKey={true}
                      />
                      <ProviderCard 
                        id="openai" title="OpenAI" description="Modelos GPT-4"
                        settings={settings} models={STATIC_MODELS['openai']}
                        requireApiKey={true}
                      />
                      <ProviderCard 
                        id="anthropic" title="Anthropic" description="Familia Claude 3"
                        settings={settings} models={STATIC_MODELS['anthropic']}
                        requireApiKey={true}
                      />
                      <ProviderCard 
                        id="gemini" title="Google Gemini" description="Gemini 1.5 Pro"
                        settings={settings} models={STATIC_MODELS['gemini']}
                        requireApiKey={true}
                      />
                      <ProviderCard 
                        id="groq" title="Groq" description="Inferencia ultrarrápida"
                        settings={settings} models={STATIC_MODELS['groq']}
                        requireApiKey={true}
                      />
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'agentes' && (
                <div className="space-y-6">
                  <h3 className="text-white text-lg border-b border-[#3c3c3c] pb-2">Agentes Inteligentes y Permisos</h3>
                  <p className="text-xs text-[#8a8a8a]">Configura los niveles de seguridad y ejecución de herramientas (Write File / PowerShell) para el agente en modo Build.</p>
                  
                  <div className="space-y-3 bg-[#252528] p-4 rounded-lg border border-[#3c3c3e]">
                    <label className="flex flex-col gap-1 text-xs">
                      <span className="font-semibold text-white">Nivel de Permisos para Herramientas (Modo Build)</span>
                      <select 
                        value={settings.permissionLevel}
                        onChange={(e) => settings.setSetting('permissionLevel', e.target.value as any)}
                        className="bg-[#1e1e1f] border border-[#3c3c3c] text-[#cccccc] px-3 py-2 rounded-lg outline-none focus:border-[#7c6ff0]"
                      >
                        <option value="ask">🛡️ Pedir Confirmación (Recomendado - Human in the Loop)</option>
                        <option value="read_only">🔒 Solo Lectura (Búsqueda y lectura de archivos sin edición/ejecución)</option>
                        <option value="auto">⚡ Autónomo Total (Ejecución libre de escrituras y PowerShell)</option>
                      </select>
                    </label>

                    <div className="text-[11px] text-[#9a9a9a] leading-relaxed bg-[#1a1a1c] p-3 rounded border border-[#3c3c3e]">
                      {settings.permissionLevel === 'ask' && (
                        <span className="text-amber-400">
                          <strong>Modo Seguro (Human-in-the-Loop):</strong> El agente te mostrará un modal de confirmación antes de editar archivos o ejecutar PowerShell para que apruebes cada acción.
                        </span>
                      )}
                      {settings.permissionLevel === 'read_only' && (
                        <span className="text-blue-400">
                          <strong>Modo Solo Lectura:</strong> El agente podrá inspeccionar archivos y realizar búsquedas web, pero la edición de archivos y ejecución de scripts estará bloqueada.
                        </span>
                      )}
                      {settings.permissionLevel === 'auto' && (
                        <span className="text-rose-400">
                          <strong>Modo Autónomo:</strong> El agente ejecutará cambios en archivos y comandos de PowerShell de forma directa sin solicitar confirmación previa.
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="bg-[#2d2d30] p-4 rounded-md flex flex-col gap-2 items-center justify-center h-28 border border-dashed border-[#3c3c3c]">
                    <Box size={20} className="text-[#a78bfa]" />
                    <span className="text-xs text-[#8a8a8a]">Registro Avanzado de Agentes Sub-Procesos (Próximamente)</span>
                  </div>
                </div>
              )}

              {activeTab === 'mcp' && (
                <div className="space-y-6">
                  <h3 className="text-white text-lg border-b border-[#3c3c3c] pb-2">Model Context Protocol (MCP)</h3>
                  <p className="text-xs text-[#8a8a8a]">Gestiona los servidores MCP conectados que extienden el contexto de la aplicación.</p>
                  <div className="bg-[#2d2d30] p-4 rounded-md flex flex-col gap-2 items-center justify-center h-32 border border-dashed border-[#3c3c3c]">
                    <Network size={24} className="text-[#a78bfa]" />
                    <span className="text-sm">Endpoints MCP (Próximamente)</span>
                  </div>
                </div>
              )}

              {activeTab === 'skills' && (
                <div className="space-y-6">
                  <h3 className="text-white text-lg border-b border-[#3c3c3c] pb-2">Skills / Habilidades</h3>
                  <p className="text-xs text-[#8a8a8a]">Habilita o deshabilita las herramientas (tools) disponibles para el agente cognitivo (ej. control de navegador, shell, acceso a bases de datos).</p>
                  <div className="bg-[#2d2d30] p-4 rounded-md flex flex-col gap-2 items-center justify-center h-32 border border-dashed border-[#3c3c3c]">
                    <Zap size={24} className="text-[#a78bfa]" />
                    <span className="text-sm">Gestor de Skills (Próximamente)</span>
                  </div>
                </div>
              )}

              {activeTab === 'emociones' && (
                <div className="space-y-6">
                  <h3 className="text-white text-lg border-b border-[#3c3c3c] pb-2">Emociones (Perfil Nervioso)</h3>
                  <p className="text-xs text-[#8a8a8a]">Define el estado base emocional y la personalidad del asistente.</p>
                  
                  <section className="space-y-4">
                    <label className="flex flex-col gap-1 text-xs max-w-xs">
                      <span className="font-semibold text-[#cccccc]">Perfil Principal</span>
                      <select 
                        value={settings.perfilNervioso}
                        onChange={(e) => settings.setSetting('perfilNervioso', e.target.value)}
                        className="bg-[#3c3c3c] border border-[#3c3c3c] text-[#cccccc] px-2 py-1.5 rounded outline-none"
                      >
                        <option value="equilibrado">Equilibrado (default)</option>
                        <option value="analitico">Analítico</option>
                        <option value="creativo">Creativo / Explorador</option>
                        <option value="defensivo">Defensivo / Cauteloso</option>
                        <option value="agresivo">Agresivo / Ofensivo</option>
                      </select>
                    </label>
                    
                    <div className="bg-[#2d2d30] p-4 rounded-md mt-4">
                      <p className="text-xs text-[#8a8a8a]">El perfil emocional afecta la toma de decisiones, la propensión a tomar riesgos durante la codificación y la empatía en las respuestas.</p>
                    </div>
                  </section>
                </div>
              )}
              
            </div>
            {/* Footer */}
            <div className="p-4 border-t border-[#3c3c3c] bg-[#252526] flex justify-end">
              <button 
                onClick={onClose}
                className="bg-[#7c6ff0] hover:bg-[#a78bfa] text-white px-6 py-2 rounded text-xs font-semibold transition-colors flex items-center gap-2"
              >
                <Check size={14} /> Guardar Cambios
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
