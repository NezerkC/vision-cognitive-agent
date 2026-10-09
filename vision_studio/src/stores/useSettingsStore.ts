import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SettingsState {
  // LLM Router
  routingStrategy: string;
  effortLevel: string;
  provider: string;
  model: string; // Active model (deprecated in favor of providerModels soon, but kept for compatibility)
  providerModels: Record<string, string>;
  apiBase: string;
  apiKeys: Record<string, string>;
  endpoints: Record<string, string>;
  
  // Oído (Mic)
  oidoMock: boolean;
  oidoDevice: string;
  oidoThreshold: number;
  oidoWhisper: string;
  
  // Habla (TTS)
  hablaMock: boolean;
  hablaDevice: string;
  hablaTts: string;
  
  // Visión (Cámara)
  visionCamaraActiva: boolean;
  visionCamaraDevice: string;
  
  // Perfil Nervioso
  perfilNervioso: string;

  // Permisos del Agente (Build / Tools)
  permissionLevel: 'read_only' | 'ask' | 'auto';

  // UI State
  isSettingsModalOpen: boolean;
  setSettingsModalOpen: (isOpen: boolean) => void;
  isSidebarVisible: boolean;
  toggleSidebar: () => void;
  setSidebarVisible: (visible: boolean) => void;
  activeSidebarTab: string;
  setActiveSidebarTab: (tab: string) => void;
  isTerminalOpen: boolean;
  setTerminalOpen: (isOpen: boolean) => void;
  llmMode: 'free' | 'hybrid' | 'paid';
  setLlmMode: (mode: 'free' | 'hybrid' | 'paid') => void;

  // Workspace / Gestor de Proyectos
  currentWorkspacePath: string;
  setCurrentWorkspacePath: (path: string) => void;
  recentProjects: string[];
  addRecentProject: (path: string) => void;

  // Motor Local (Llama.cpp / Ollama / LM Studio)
  llamacppFolderPath: string;
  llamacppModelPath: string;
  llamacppPreset: string;
  llamacppNgl: number;
  llamacppContextSize: number;
  llamacppKvCache: string;
  llamacppFlashAttention: boolean;
  llamacppMtpEnabled: boolean;
  llamacppMtpDraftMax: number;
  llamacppTemperature: number;
  llamacppTopP: number;
  llamacppPort: number;
  llamacppHost: string;
  llamacppServerStatus: 'stopped' | 'loading' | 'running' | 'error';
  customBatPresets: { id: string; name: string; config: any }[];

  // Acciones
  setSetting: <K extends keyof Omit<SettingsState, 'setSetting' | 'setApiKey' | 'setProviderModel' | 'setSettingsModalOpen' | 'setActiveSidebarTab' | 'setTerminalOpen' | 'setLlmMode' | 'setEndpoint' | 'addCustomBatPreset'>>(key: K, value: SettingsState[K]) => void;
  setApiKey: (provider: string, key: string) => void;
  setEndpoint: (provider: string, url: string) => void;
  setProviderModel: (provider: string, model: string) => void;
  addCustomBatPreset: (preset: { id: string; name: string; config: any }) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      isSettingsModalOpen: false,
      setSettingsModalOpen: (isOpen) => set({ isSettingsModalOpen: isOpen }),
      isSidebarVisible: true,
      toggleSidebar: () => set((state) => ({ isSidebarVisible: !state.isSidebarVisible })),
      setSidebarVisible: (visible) => set({ isSidebarVisible: visible }),
      activeSidebarTab: 'explorer',
      setActiveSidebarTab: (tab) => set({ activeSidebarTab: tab, isSidebarVisible: true }),
      isTerminalOpen: true,
      setTerminalOpen: (isOpen) => set({ isTerminalOpen: isOpen }),
      llmMode: 'hybrid',
      setLlmMode: (mode) => set({ llmMode: mode }),

      // Workspace / Gestor de Proyectos
      currentWorkspacePath: 'C:\\Users\\lolpl\\Desktop\\02_Proyectos_Dev\\vision-cognitive-agent',
      setCurrentWorkspacePath: (path) => set({ currentWorkspacePath: path }),
      recentProjects: [
        'C:\\Users\\lolpl\\Desktop\\02_Proyectos_Dev\\vision-cognitive-agent'
      ],
      addRecentProject: (path) => set((state) => {
        const filtered = (state.recentProjects || []).filter(p => p !== path);
        return { recentProjects: [path, ...filtered].slice(0, 8) };
      }),
      routingStrategy: 'locales',
      effortLevel: 'esfuerzo_medio',
      provider: 'ollama',
      model: 'llama3.2:latest',
      providerModels: {
        ollama: 'llama3.2:latest',
        openrouter: 'google/gemini-1.5-pro',
        openai: 'gpt-4o',
        llamacpp: 'gemma-2-9b-it'
      },
      apiBase: '',
      apiKeys: {},
      endpoints: {
        ollama: 'http://localhost:11434',
        llamacpp: 'http://localhost:8080/v1',
        lmstudio: 'http://localhost:1234/v1'
      },
      
      oidoMock: true,
      oidoDevice: 'default',
      oidoThreshold: 300,
      oidoWhisper: 'base',
      
      hablaMock: true,
      hablaDevice: 'default',
      hablaTts: 'edge-tts',
      
      visionCamaraActiva: false,
      visionCamaraDevice: 'default',
      
      perfilNervioso: 'equilibrado',
      permissionLevel: 'ask',
      
      // Motor Local (Llama.cpp / Ollama / LM Studio)
      llamacppFolderPath: 'C:\\Users\\lolpl\\Desktop\\llama.cpp\\llama-b10082-bin-win-cuda-13.3-x64',
      llamacppModelPath: 'C:\\Users\\lolpl\\Desktop\\llama.cpp\\llama-b10082-bin-win-cuda-13.3-x64\\gguf\\qwen3.6-35B-A3B\\Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf',
      llamacppPreset: 'qwen_35b',
      llamacppNgl: 999,
      llamacppContextSize: 131072,
      llamacppKvCache: 'q4_0',
      llamacppFlashAttention: true,
      llamacppMtpEnabled: true,
      llamacppMtpDraftMax: 2,
      llamacppTemperature: 0.7,
      llamacppTopP: 0.9,
      llamacppPort: 8080,
      llamacppHost: '127.0.0.1',
      llamacppServerStatus: 'stopped',
      customBatPresets: [
        { id: 'custom-qwen-35b-opt', name: 'Mi Config Qwen 35B Optimizada', config: { ngl: 999, c: 131072, ctk: 'q4_0', ctv: 'q4_0', fa: true, mtp: true, mtpDraftMax: 2, temp: 0.7, topP: 0.8 } }
      ],

      setSetting: (key, value) => set((state) => ({ ...state, [key]: value })),
      setApiKey: (provider, key) => set((state) => ({ 
        apiKeys: { ...state.apiKeys, [provider]: key } 
      })),
      setEndpoint: (provider, url) => set((state) => ({
        endpoints: { ...state.endpoints, [provider]: url }
      })),
      setProviderModel: (provider, model) => set((state) => ({
        providerModels: { ...state.providerModels, [provider]: model },
        ...(state.provider === provider ? { model } : {})
      })),
      addCustomBatPreset: (preset) => set((state) => ({
        customBatPresets: [...(state.customBatPresets || []), preset]
      })),
    }),
    {
      name: 'vision-os-settings',
    }
  )
);
