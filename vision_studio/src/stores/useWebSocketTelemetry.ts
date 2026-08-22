import { create } from 'zustand';

export interface MemoryNode4D {
  text: string;
  x: number;
  y: number;
  z: number;
  w: number;
}

export interface TelemetryData {
  cpu_pct?: number;
  ram_pct?: number;
  vram_pct?: number;
  gpu_temp?: number;
  vram_used_gb?: number;
  vram_total_gb?: number;
}

export interface EmotionState {
  estado: string;
  intensidad: number;
  rueda_plutchik?: {
    alegria?: number;
    confianza?: number;
    miedo?: number;
    sorpresa?: number;
    tristeza?: number;
    disgusto?: number;
    ira?: number;
    anticipacion?: number;
  };
}

interface TelemetryStore {
  gpuName: string;
  telemetry: TelemetryData;
  emotion: EmotionState | null;
  memoryNodes: MemoryNode4D[];
  isConnected: boolean;
  setTelemetryData: (data: {
    gpu_name?: string;
    telemetry?: TelemetryData;
    emotion?: EmotionState;
    memory_nodes?: MemoryNode4D[];
  }) => void;
  setIsConnected: (connected: boolean) => void;
}

export const useWebSocketTelemetry = create<TelemetryStore>((set) => ({
  gpuName: 'NVIDIA GeForce RTX 5060 Ti',
  telemetry: {
    cpu_pct: 12.4,
    ram_pct: 38.2,
    vram_pct: 28.5,
    gpu_temp: 46.0,
    vram_used_gb: 4.56,
    vram_total_gb: 16.0,
  },
  emotion: {
    estado: 'Neutral',
    intensidad: 0.5,
    rueda_plutchik: {
      alegria: 0.5,
      confianza: 0.7,
      miedo: 0.1,
      sorpresa: 0.3,
      tristeza: 0.0,
      disgusto: 0.0,
      ira: 0.0,
      anticipacion: 0.6,
    },
  },
  memoryNodes: [],
  isConnected: false,

  setTelemetryData: (data) =>
    set((state) => ({
      gpuName: data.gpu_name || state.gpuName,
      telemetry: data.telemetry ? { ...state.telemetry, ...data.telemetry } : state.telemetry,
      emotion: data.emotion || state.emotion,
      memoryNodes: data.memory_nodes && data.memory_nodes.length > 0 ? data.memory_nodes : state.memoryNodes,
    })),

  setIsConnected: (connected) => set({ isConnected: connected }),
}));
