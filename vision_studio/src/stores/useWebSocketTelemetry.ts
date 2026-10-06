import { create } from 'zustand';

export interface MemoryNode4D {
  text: string;
  x: number;
  y: number;
  z: number;
  w: number;
}

/** Hardware readings as sent by the gateway (cognitivo/gestor_llamacpp.py). null means not available. */
export interface TelemetryData {
  cpuPercent?: number | null;
  ramUsedGb?: number | null;
  ramTotalGb?: number | null;
  ramPercent?: number | null;
  gpuName?: string | null;
  vramUsedGb?: number | null;
  vramTotalGb?: number | null;
  vramPercent?: number | null;
  gpuTemp?: number | null;
  cpuTemp?: number | null;
  disks?: { name: string; freeGb: number; totalGb: number; percent: number }[];
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
  gpuName: string | null;
  telemetry: TelemetryData;
  emotion: EmotionState | null;
  memoryNodes: MemoryNode4D[];
  isConnected: boolean;
  setTelemetryData: (data: {
    gpu_name?: string | null;
    telemetry?: TelemetryData;
    emotion?: EmotionState;
    memory_nodes?: MemoryNode4D[];
  }) => void;
  setIsConnected: (connected: boolean) => void;
}

// No readings until the gateway sends them: the HUD shows dashes instead of plausible-looking numbers.
export const useWebSocketTelemetry = create<TelemetryStore>((set) => ({
  gpuName: null,
  telemetry: {},
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
      gpuName: data.gpu_name !== undefined ? data.gpu_name : state.gpuName,
      telemetry: data.telemetry ?? state.telemetry,
      emotion: data.emotion || state.emotion,
      memoryNodes: data.memory_nodes && data.memory_nodes.length > 0 ? data.memory_nodes : state.memoryNodes,
    })),

  setIsConnected: (connected) => set({ isConnected: connected }),
}));
