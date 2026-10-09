import { useState } from 'react';
import { 
  Brain, 
  Layers, 
  Terminal, 
  Search, 
  Activity, 
  Zap, 
  Network, 
  Play, 
  FileCode, 
  Database,
  Sparkles
} from 'lucide-react';

export interface ScriptCarril {
  id: string;
  name: string;
  scriptPath: string;
  sourceLobe: 'frontal' | 'parietal' | 'izquierdo' | 'sentidos' | 'temporal';
  targetLobe: 'frontal' | 'parietal' | 'izquierdo' | 'sentidos' | 'temporal';
  status: 'idle' | 'pulsing' | 'completed';
  complexity: 'express' | 'entrelazado';
  agentName: string;
  vagonInfo?: {
    inputQuery?: string;
    payloadData?: string;
    outputSummary?: string;
    executionTimeMs?: number;
  };
}

const INITIAL_CARRILES: ScriptCarril[] = [
  {
    id: 'carril-rag',
    name: 'Carril RAG & Vectorial',
    scriptPath: 'cognitivo/memoria.py',
    sourceLobe: 'frontal',
    targetLobe: 'parietal',
    status: 'completed',
    complexity: 'express',
    agentName: 'AgenteParietalRAG',
    vagonInfo: {
      inputQuery: '¿Cómo configurar la memoria LanceDB?',
      payloadData: 'Vagón #1: 3 vectores de alta similitud cosine (0.92)',
      outputSummary: 'Contexto de memoria recuperado con éxito.',
      executionTimeMs: 142
    }
  },
  {
    id: 'carril-web',
    name: 'Carril Percepción Web',
    scriptPath: 'cognitivo/skills/websearch_tool.py',
    sourceLobe: 'frontal',
    targetLobe: 'sentidos',
    status: 'pulsing',
    complexity: 'entrelazado',
    agentName: 'AgenteSentidosWeb',
    vagonInfo: {
      inputQuery: 'Documentación oficial FastAPI WebSockets',
      payloadData: 'Vagón #2: HTML parsed & 4 chunks formateados',
      outputSummary: 'Búsqueda web en curso...',
      executionTimeMs: 380
    }
  },
  {
    id: 'carril-cli',
    name: 'Carril Ejecución Sandbox',
    scriptPath: 'cognitivo/ejecutor_izquierdo.py',
    sourceLobe: 'frontal',
    targetLobe: 'izquierdo',
    status: 'idle',
    complexity: 'entrelazado',
    agentName: 'AgenteHemisferioIzquierdo',
    vagonInfo: {
      inputQuery: 'pytest tests/test_orquestador_graph.py',
      payloadData: 'Vagón #3: Script de prueba en cola sandbox',
      outputSummary: 'Esperando activación de pulso.',
      executionTimeMs: 0
    }
  },
  {
    id: 'carril-logs',
    name: 'Carril Homeostasis & Logs',
    scriptPath: 'core/broker_eventos.py',
    sourceLobe: 'parietal',
    targetLobe: 'temporal',
    status: 'completed',
    complexity: 'express',
    agentName: 'AgenteTemporalHomeostasis',
    vagonInfo: {
      inputQuery: 'Telemetría de eventos TCP',
      payloadData: 'Vagón #4: Evento HEARTBEAT registrado',
      outputSummary: 'Estado de homeostasis: Equilibrado.',
      executionTimeMs: 45
    }
  }
];

export default function AgentsSynapticView() {
  const [carriles, setCarriles] = useState<ScriptCarril[]>(INITIAL_CARRILES);
  const [selectedCarrilId, setSelectedCarrilId] = useState<string | null>('carril-web');
  const [queryInput, setQueryInput] = useState<string>('Analizar arquitectura de agentes y ejecutar tests');
  const [pulseType, setPulseType] = useState<'express' | 'entrelazado'>('entrelazado');
  const [isPulsing, setIsPulsing] = useState<boolean>(false);
  const [activeLobe, setActiveLobe] = useState<string>('frontal');

  const triggerQueryPulse = () => {
    setIsPulsing(true);
    setActiveLobe('frontal');

    // Reset status
    setCarriles(prev => prev.map(c => ({ ...c, status: 'idle' })));

    if (pulseType === 'express') {
      // Express pulse: frontal -> parietal -> done
      setTimeout(() => {
        setCarriles(prev => prev.map(c => c.id === 'carril-rag' ? { ...c, status: 'pulsing' } : c));
        setActiveLobe('parietal');
      }, 400);

      setTimeout(() => {
        setCarriles(prev => prev.map(c => c.id === 'carril-rag' ? { ...c, status: 'completed' } : c));
        setIsPulsing(false);
      }, 1500);
    } else {
      // Multi-lobe complex pulse
      setTimeout(() => {
        setCarriles(prev => prev.map(c => c.id === 'carril-rag' || c.id === 'carril-web' ? { ...c, status: 'pulsing' } : c));
        setActiveLobe('sentidos');
      }, 400);

      setTimeout(() => {
        setCarriles(prev => prev.map(c => c.id === 'carril-cli' ? { ...c, status: 'pulsing' } : c));
        setActiveLobe('izquierdo');
      }, 1200);

      setTimeout(() => {
        setCarriles(prev => prev.map(c => ({ ...c, status: 'completed' })));
        setActiveLobe('temporal');
        setIsPulsing(false);
      }, 2400);
    }
  };

  const selectedCarril = carriles.find(c => c.id === selectedCarrilId);

  return (
    <div className="h-full w-full bg-[#18181b] text-[#cccccc] flex flex-col overflow-hidden select-none font-sans">
      {/* Header / Query Bar */}
      <div className="p-3 bg-[#202023] border-b border-[#3f3f46] flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Brain className="text-purple-400 animate-pulse" size={22} />
          <div>
            <h2 className="font-semibold text-sm tracking-wide text-white flex items-center gap-2">
              MAPA CEREBRAL & CARRILES DE SCRIPTS
            </h2>
            <p className="text-[11px] text-gray-400">Pulso de Query conducido por agentes y scripts Python</p>
          </div>
        </div>

        {/* Query Pulse Dispatcher */}
        <div className="flex items-center gap-2 flex-1 max-w-xl">
          <div className="relative flex-1">
            <input 
              type="text"
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              placeholder="Escribe la query para disparar el pulso..."
              className="w-full bg-[#18181b] border border-[#3f3f46] focus:border-purple-500 rounded text-xs px-3 py-1.5 pr-8 text-white outline-none"
            />
            <Sparkles size={14} className="absolute right-2.5 top-2 text-purple-400" />
          </div>

          <div className="flex items-center bg-[#18181b] border border-[#3f3f46] rounded p-0.5 text-xs">
            <button
              onClick={() => setPulseType('express')}
              className={`px-2 py-1 rounded text-[11px] flex items-center gap-1 transition-colors ${pulseType === 'express' ? 'bg-amber-500/20 text-amber-300 font-medium border border-amber-500/40' : 'text-gray-400 hover:text-white'}`}
            >
              <Zap size={10} /> Express ⚡
            </button>
            <button
              onClick={() => setPulseType('entrelazado')}
              className={`px-2 py-1 rounded text-[11px] flex items-center gap-1 transition-colors ${pulseType === 'entrelazado' ? 'bg-purple-500/20 text-purple-300 font-medium border border-purple-500/40' : 'text-gray-400 hover:text-white'}`}
            >
              <Network size={10} /> Multilóbulo 🕸️
            </button>
          </div>

          <button 
            onClick={triggerQueryPulse}
            disabled={isPulsing}
            className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded flex items-center gap-1.5 font-medium transition-colors shadow-lg shadow-purple-900/30"
          >
            <Play size={13} fill="currentColor" /> {isPulsing ? 'Disparando...' : 'Disparar Pulso'}
          </button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Side: Interactive Brain Map Topography */}
        <div className="flex-1 relative bg-[#0f0f11] p-6 flex items-center justify-center overflow-hidden border-r border-[#27272a]">
          {/* Subtle Grid Background */}
          <div className="absolute inset-0 bg-[radial-gradient(#27272a_1px,transparent_1px)] [background-size:20px_20px] opacity-40"></div>

          {/* Brain Map Container */}
          <div className="relative w-full max-w-2xl h-[420px] border border-[#27272a] bg-[#141417]/80 rounded-2xl p-6 shadow-2xl flex flex-col justify-between">
            {/* Lóbulo Frontal (Top Center) */}
            <div className="flex justify-center">
              <div className={`p-3 rounded-xl border transition-all duration-300 flex items-center gap-3 shadow-lg ${activeLobe === 'frontal' ? 'bg-purple-950/80 border-purple-400 shadow-purple-500/30 scale-105' : 'bg-[#1f1f23] border-[#3f3f46]'}`}>
                <div className="p-2 bg-purple-900/60 rounded-lg text-purple-300">
                  <Brain size={24} />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-white tracking-wide">LÓBULO FRONTAL</h3>
                  <span className="text-[10px] text-purple-300">Decisión & Router LLM</span>
                </div>
              </div>
            </div>

            {/* Middle Row: Parietal (Right) & Hemisferio Izquierdo (Left) */}
            <div className="flex justify-between items-center px-4">
              {/* Hemisferio Izquierdo (Left) */}
              <div className={`p-3 rounded-xl border transition-all duration-300 flex items-center gap-3 shadow-lg ${activeLobe === 'izquierdo' ? 'bg-emerald-950/80 border-emerald-400 shadow-emerald-500/30 scale-105' : 'bg-[#1f1f23] border-[#3f3f46]'}`}>
                <div className="p-2 bg-emerald-900/60 rounded-lg text-emerald-300">
                  <Terminal size={24} />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-white tracking-wide">HEMISFERIO IZQ.</h3>
                  <span className="text-[10px] text-emerald-300">Ejecutor CLI & Scripts</span>
                </div>
              </div>

              {/* Lóbulo Temporal (Center / Homeostasis) */}
              <div className={`p-2.5 rounded-xl border transition-all duration-300 flex items-center gap-2 shadow-lg ${activeLobe === 'temporal' ? 'bg-rose-950/80 border-rose-400 shadow-rose-500/30 scale-105' : 'bg-[#1c1c20] border-[#3f3f46]'}`}>
                <Activity size={18} className="text-rose-400 animate-pulse" />
                <span className="text-[11px] font-semibold text-rose-200">Temporal (Logs/Homeostasis)</span>
              </div>

              {/* Lóbulo Parietal (Right) */}
              <div className={`p-3 rounded-xl border transition-all duration-300 flex items-center gap-3 shadow-lg ${activeLobe === 'parietal' ? 'bg-cyan-950/80 border-cyan-400 shadow-cyan-500/30 scale-105' : 'bg-[#1f1f23] border-[#3f3f46]'}`}>
                <div className="p-2 bg-cyan-900/60 rounded-lg text-cyan-300">
                  <Layers size={24} />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-white tracking-wide">LÓBULO PARIETAL</h3>
                  <span className="text-[10px] text-cyan-300">Memoria Vectorial (LanceDB)</span>
                </div>
              </div>
            </div>

            {/* Bottom Row: Sentidos (Center / Bottom) */}
            <div className="flex justify-center">
              <div className={`p-3 rounded-xl border transition-all duration-300 flex items-center gap-3 shadow-lg ${activeLobe === 'sentidos' ? 'bg-amber-950/80 border-amber-400 shadow-amber-500/30 scale-105' : 'bg-[#1f1f23] border-[#3f3f46]'}`}>
                <div className="p-2 bg-amber-900/60 rounded-lg text-amber-300">
                  <Search size={24} />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-white tracking-wide">SENTIDOS (PERCEPCIÓN)</h3>
                  <span className="text-[10px] text-amber-300">Búsqueda Web & Scraper</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Carriles de Scripts & Payload Inspector */}
        <div className="w-[360px] bg-[#18181b] flex flex-col overflow-hidden border-l border-[#27272a]">
          {/* Header Carriles */}
          <div className="p-3 bg-[#202023] border-b border-[#27272a] flex items-center justify-between">
            <span className="text-xs font-bold text-white flex items-center gap-1.5 uppercase tracking-wide">
              <FileCode size={14} className="text-purple-400" /> Carriles de Scripts
            </span>
            <span className="text-[10px] text-gray-400 bg-[#141417] px-2 py-0.5 rounded border border-[#27272a]">
              {carriles.length} Vías Neurales
            </span>
          </div>

          {/* Carriles Stream List */}
          <div className="p-3 space-y-2 border-b border-[#27272a] max-h-64 overflow-y-auto no-scrollbar">
            {carriles.map(carril => (
              <div 
                key={carril.id}
                onClick={() => setSelectedCarrilId(carril.id)}
                className={`p-2.5 rounded-lg border cursor-pointer transition-all ${selectedCarrilId === carril.id ? 'bg-purple-950/40 border-purple-500/80 shadow-md' : 'bg-[#202023] border-[#27272a] hover:border-[#3f3f46]'}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-white flex items-center gap-1">
                    {carril.name}
                  </span>
                  {carril.status === 'pulsing' && (
                    <span className="bg-purple-500/20 text-purple-300 border border-purple-500/40 text-[9px] px-1.5 py-0.2 rounded-full animate-pulse flex items-center gap-1">
                      <Sparkles size={8} /> Pulso Activo
                    </span>
                  )}
                  {carril.status === 'completed' && (
                    <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[9px] px-1.5 py-0.2 rounded-full">
                      ✓ Completado
                    </span>
                  )}
                  {carril.status === 'idle' && (
                    <span className="text-gray-500 text-[9px]">Reposo</span>
                  )}
                </div>

                <div className="text-[10px] font-mono text-gray-400 flex items-center gap-1 truncate">
                  <FileCode size={11} className="text-gray-500 flex-shrink-0" />
                  {carril.scriptPath}
                </div>

                <div className="flex items-center justify-between mt-2 pt-1 border-t border-[#27272a] text-[10px] text-gray-400">
                  <span>Agente: <strong className="text-purple-300">{carril.agentName}</strong></span>
                  <span className="text-gray-500">{carril.vagonInfo?.executionTimeMs}ms</span>
                </div>
              </div>
            ))}
          </div>

          {/* Inspector del Vagón de Información */}
          <div className="flex-1 p-3 bg-[#121214] overflow-y-auto space-y-2">
            <h4 className="text-xs font-semibold text-purple-300 flex items-center gap-1.5 uppercase tracking-wide">
              <Database size={13} /> Inspector del Vagón de Información
            </h4>

            {selectedCarril ? (
              <div className="space-y-2 text-xs">
                <div className="bg-[#18181b] p-2.5 border border-[#27272a] rounded space-y-1">
                  <div className="text-[10px] font-semibold text-gray-400 uppercase">Script & Agente</div>
                  <div className="text-white font-mono text-[11px]">{selectedCarril.scriptPath}</div>
                  <div className="text-purple-300 text-[11px] font-semibold">{selectedCarril.agentName}</div>
                </div>

                {selectedCarril.vagonInfo && (
                  <>
                    <div className="bg-[#18181b] p-2.5 border border-[#27272a] rounded space-y-1">
                      <div className="text-[10px] font-semibold text-blue-400 uppercase">Input de la Query</div>
                      <div className="text-gray-200 text-[11px]">{selectedCarril.vagonInfo.inputQuery}</div>
                    </div>

                    <div className="bg-[#18181b] p-2.5 border border-[#27272a] rounded space-y-1">
                      <div className="text-[10px] font-semibold text-emerald-400 uppercase">Payload Transmitido</div>
                      <div className="text-emerald-200 font-mono text-[10px] bg-black/40 p-2 rounded border border-[#27272a]">
                        {selectedCarril.vagonInfo.payloadData}
                      </div>
                    </div>

                    <div className="bg-[#18181b] p-2.5 border border-[#27272a] rounded space-y-1">
                      <div className="text-[10px] font-semibold text-purple-400 uppercase">Resultado / Síntesis</div>
                      <div className="text-gray-300 text-[11px]">{selectedCarril.vagonInfo.outputSummary}</div>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="text-xs text-gray-500 p-4 text-center">
                Selecciona un carril para auditar su vagón de información.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
