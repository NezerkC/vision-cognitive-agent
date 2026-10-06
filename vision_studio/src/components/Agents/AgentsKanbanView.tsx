import { useState } from 'react';
import { 
  Bot, 
  Brain, 
  Search, 
  Terminal, 
  Clock, 
  Zap, 
  Network, 
  ChevronDown, 
  ChevronUp, 
  Plus, 
  Filter,
  Layers,
  Activity
} from 'lucide-react';

export interface AgentTask {
  id: string;
  title: string;
  description: string;
  complexity: 'express' | 'entrelazado';
  lobe: 'frontal' | 'parietal' | 'izquierdo' | 'sentidos' | 'temporal';
  column: 'backlog' | 'planning' | 'in_progress' | 'verifying' | 'completed';
  payload?: {
    input?: string;
    output?: string;
    vagonesInfo?: string[];
  };
  updatedAt: string;
}

const INITIAL_TASKS: AgentTask[] = [
  {
    id: 'task-1',
    title: 'Consultar contexto previo de RAG (LanceDB)',
    description: 'Recuperar embeddings relacionados con la configuración del motor local.',
    complexity: 'express',
    lobe: 'parietal',
    column: 'completed',
    payload: {
      input: '¿Cómo configurar llama.cpp con Qwen 35B?',
      output: 'Encontrados 3 vectores relevantes en memoria activa.',
      vagonesInfo: ['Vagón #1: lancedb_chunk_84.json', 'Vagón #2: presets_llama.json']
    },
    updatedAt: 'Hace 5m'
  },
  {
    id: 'task-2',
    title: 'Descomponer consulta compleja en sub-tareas',
    description: 'Enrutado dinámico mediante LLM Router para decidir lóbulos a activar.',
    complexity: 'entrelazado',
    lobe: 'frontal',
    column: 'in_progress',
    payload: {
      input: 'Analizar logs de terminal y buscar solución en la web',
      output: 'Grafo planificado: [Memoria ➔ Web ➔ Terminal Exec]',
      vagonesInfo: ['Vagón #1: prompt_descomposicion.txt']
    },
    updatedAt: 'Justo ahora'
  },
  {
    id: 'task-3',
    title: 'Búsqueda web activa sobre documentación FastAPI',
    description: 'Consultar endpoints de WebSocket para telemetría de eventos.',
    complexity: 'express',
    lobe: 'sentidos',
    column: 'in_progress',
    payload: {
      input: 'fastapi websocket event broker architecture',
      output: 'Obtenidos 4 resultados de Tavily Search.',
      vagonesInfo: ['Vagón #1: web_results.json']
    },
    updatedAt: 'Hace 2m'
  },
  {
    id: 'task-4',
    title: 'Ejecutar test suite de Pytest en Sandbox',
    description: 'Correr tests del orquestador graph en el Hemisferio Izquierdo.',
    complexity: 'entrelazado',
    lobe: 'izquierdo',
    column: 'planning',
    payload: {
      input: 'pytest tests/test_orquestador_graph.py',
      output: 'Esperando finalización de planificación...',
      vagonesInfo: []
    },
    updatedAt: 'Hace 1m'
  },
  {
    id: 'task-5',
    title: 'Auditoría de sintaxis y tipado TypeScript',
    description: 'Validar componentes en el sub-sistema vision_studio.',
    complexity: 'express',
    lobe: 'izquierdo',
    column: 'backlog',
    payload: {
      input: 'npx tsc --noEmit',
      output: 'En cola de tareas.',
      vagonesInfo: []
    },
    updatedAt: 'Hace 10m'
  }
];

export default function AgentsKanbanView() {
  const [tasks, setTasks] = useState<AgentTask[]>(INITIAL_TASKS);
  const [filterComplexity, setFilterComplexity] = useState<'all' | 'express' | 'entrelazado'>('all');
  const [expandedPayload, setExpandedPayload] = useState<string | null>(null);

  const columns = [
    { id: 'backlog', title: '📋 Backlog / Pendientes', color: 'border-gray-600' },
    { id: 'planning', title: '🧠 Planificación (Lóbulo Frontal)', color: 'border-purple-500' },
    { id: 'in_progress', title: '⚡ En Ejecución (Lóbulos Activos)', color: 'border-blue-500' },
    { id: 'verifying', title: '🔍 Verificación y Síntesis', color: 'border-amber-500' },
    { id: 'completed', title: '✅ Completado', color: 'border-emerald-500' },
  ];

  const getLobeBadge = (lobe: AgentTask['lobe']) => {
    switch (lobe) {
      case 'frontal':
        return <span className="bg-purple-900/60 text-purple-300 text-[10px] px-1.5 py-0.5 rounded border border-purple-700/50 flex items-center gap-1"><Brain size={10} /> Frontal</span>;
      case 'parietal':
        return <span className="bg-cyan-900/60 text-cyan-300 text-[10px] px-1.5 py-0.5 rounded border border-cyan-700/50 flex items-center gap-1"><Layers size={10} /> Parietal (RAG)</span>;
      case 'izquierdo':
        return <span className="bg-emerald-900/60 text-emerald-300 text-[10px] px-1.5 py-0.5 rounded border border-emerald-700/50 flex items-center gap-1"><Terminal size={10} /> Izquierdo (CLI)</span>;
      case 'sentidos':
        return <span className="bg-amber-900/60 text-amber-300 text-[10px] px-1.5 py-0.5 rounded border border-amber-700/50 flex items-center gap-1"><Search size={10} /> Sentidos (Web)</span>;
      case 'temporal':
        return <span className="bg-rose-900/60 text-rose-300 text-[10px] px-1.5 py-0.5 rounded border border-rose-700/50 flex items-center gap-1"><Activity size={10} /> Temporal (Logs)</span>;
    }
  };

  const moveTask = (taskId: string, direction: 'next' | 'prev') => {
    const colOrder: AgentTask['column'][] = ['backlog', 'planning', 'in_progress', 'verifying', 'completed'];
    setTasks(prev => prev.map(t => {
      if (t.id !== taskId) return t;
      const idx = colOrder.indexOf(t.column);
      const newIdx = direction === 'next' ? Math.min(colOrder.length - 1, idx + 1) : Math.max(0, idx - 1);
      return { ...t, column: colOrder[newIdx], updatedAt: 'Justo ahora' };
    }));
  };

  const filteredTasks = tasks.filter(t => filterComplexity === 'all' || t.complexity === filterComplexity);

  return (
    <div className="h-full w-full bg-[#1e1e1e] text-[#cccccc] flex flex-col overflow-hidden select-none font-sans">
      {/* Header Bar */}
      <div className="p-3 bg-[#252526] border-b border-[#3c3c3c] flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Bot className="text-purple-400" size={20} />
          <h2 className="font-semibold text-sm tracking-wide text-white">AGENTES ENTRELAZADORES (TABLERO KANBAN)</h2>
          <span className="bg-purple-900/40 text-purple-300 text-xs px-2 py-0.5 rounded-full border border-purple-500/30">
            {filteredTasks.length} Tareas Activas
          </span>
        </div>

        {/* Dynamic Filters & Actions */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-[#1e1e1e] border border-[#3c3c3c] rounded p-1 text-xs">
            <Filter size={12} className="text-gray-400 ml-1" />
            <button 
              onClick={() => setFilterComplexity('all')}
              className={`px-2 py-0.5 rounded text-[11px] transition-colors ${filterComplexity === 'all' ? 'bg-[#3c3c3c] text-white font-medium' : 'text-gray-400 hover:text-white'}`}
            >
              Todos
            </button>
            <button 
              onClick={() => setFilterComplexity('express')}
              className={`px-2 py-0.5 rounded text-[11px] flex items-center gap-1 transition-colors ${filterComplexity === 'express' ? 'bg-amber-500/20 text-amber-300 font-medium border border-amber-500/40' : 'text-gray-400 hover:text-white'}`}
            >
              <Zap size={10} /> Express
            </button>
            <button 
              onClick={() => setFilterComplexity('entrelazado')}
              className={`px-2 py-0.5 rounded text-[11px] flex items-center gap-1 transition-colors ${filterComplexity === 'entrelazado' ? 'bg-purple-500/20 text-purple-300 font-medium border border-purple-500/40' : 'text-gray-400 hover:text-white'}`}
            >
              <Network size={10} /> Entrelazado
            </button>
          </div>

          <button 
            onClick={() => {
              const newTask: AgentTask = {
                id: `task-${Date.now()}`,
                title: 'Nueva Tarea de Agente Directo',
                description: 'Ejecución enviada al backlog de trabajo.',
                complexity: 'express',
                lobe: 'frontal',
                column: 'backlog',
                updatedAt: 'Justo ahora'
              };
              setTasks([newTask, ...tasks]);
            }}
            className="bg-purple-600 hover:bg-purple-500 text-white text-xs px-2.5 py-1 rounded flex items-center gap-1 font-medium transition-colors"
          >
            <Plus size={14} /> Crear Tarea
          </button>
        </div>
      </div>

      {/* Kanban Board Container */}
      <div className="flex-1 p-3 overflow-x-auto overflow-y-hidden flex gap-3 no-scrollbar">
        {columns.map(col => {
          const colTasks = filteredTasks.filter(t => t.column === col.id);

          return (
            <div 
              key={col.id}
              className="flex-1 min-w-[260px] max-w-[320px] bg-[#252526] border border-[#3c3c3c] rounded-lg flex flex-col overflow-hidden shadow-lg"
            >
              {/* Column Header */}
              <div className={`p-2.5 bg-[#2d2d2d] border-t-2 ${col.color} flex items-center justify-between border-b border-[#3c3c3c]`}>
                <span className="text-xs font-semibold text-gray-200 tracking-wide">{col.title}</span>
                <span className="bg-[#1e1e1e] text-gray-400 text-[11px] px-2 py-0.5 rounded-full border border-[#3c3c3c]">
                  {colTasks.length}
                </span>
              </div>

              {/* Column Cards Stream */}
              <div className="flex-1 p-2 overflow-y-auto space-y-2 no-scrollbar">
                {colTasks.length === 0 ? (
                  <div className="h-24 border border-dashed border-[#3c3c3c] rounded flex items-center justify-center text-xs text-gray-500">
                    Sin agentes en este estado
                  </div>
                ) : (
                  colTasks.map(task => (
                    <div 
                      key={task.id}
                      className="bg-[#1e1e1e] border border-[#3c3c3c] hover:border-[#555555] rounded-md p-3 space-y-2 shadow transition-all relative group"
                    >
                      {/* Card Header: Badges */}
                      <div className="flex items-center justify-between gap-1 flex-wrap">
                        {getLobeBadge(task.lobe)}

                        {task.complexity === 'express' ? (
                          <span className="bg-amber-950/60 text-amber-400 border border-amber-800/60 text-[10px] px-1.5 py-0.5 rounded flex items-center gap-0.5 font-medium">
                            <Zap size={10} /> Express ⚡
                          </span>
                        ) : (
                          <span className="bg-purple-950/60 text-purple-400 border border-purple-800/60 text-[10px] px-1.5 py-0.5 rounded flex items-center gap-0.5 font-medium">
                            <Network size={10} /> Entrelazado 🕸️
                          </span>
                        )}
                      </div>

                      {/* Card Content */}
                      <h4 className="text-xs font-semibold text-white leading-snug">{task.title}</h4>
                      <p className="text-[11px] text-gray-400 leading-relaxed">{task.description}</p>

                      {/* Expandable Payload Section */}
                      {task.payload && (
                        <div className="pt-1 border-t border-[#2e2e2e]">
                          <button 
                            onClick={() => setExpandedPayload(expandedPayload === task.id ? null : task.id)}
                            className="text-[10px] text-purple-400 hover:text-purple-300 flex items-center gap-1"
                          >
                            {expandedPayload === task.id ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                            Vagón de Información ({task.payload.vagonesInfo?.length || 0})
                          </button>

                          {expandedPayload === task.id && (
                            <div className="mt-1.5 bg-[#141414] border border-[#333333] rounded p-2 text-[10px] font-mono space-y-1 text-gray-300">
                              {task.payload.input && (
                                <div><span className="text-blue-400">Input:</span> {task.payload.input}</div>
                              )}
                              {task.payload.output && (
                                <div><span className="text-emerald-400">Output:</span> {task.payload.output}</div>
                              )}
                              {task.payload.vagonesInfo && task.payload.vagonesInfo.length > 0 && (
                                <div className="pt-1 border-t border-[#252526]">
                                  <div className="text-purple-400 font-semibold mb-0.5">Vagones adjuntos:</div>
                                  {task.payload.vagonesInfo.map((v, i) => (
                                    <div key={i} className="text-gray-400 truncate">• {v}</div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Card Footer: Timestamp & Movement Controls */}
                      <div className="flex items-center justify-between pt-1 text-[10px] text-gray-500">
                        <span className="flex items-center gap-1"><Clock size={10} /> {task.updatedAt}</span>

                        <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100 transition-opacity">
                          {task.column !== 'backlog' && (
                            <button 
                              onClick={() => moveTask(task.id, 'prev')}
                              className="px-1.5 py-0.5 bg-[#2d2d2d] hover:bg-[#3d3d3d] rounded text-gray-300"
                              title="Mover a etapa anterior"
                            >
                              ◀
                            </button>
                          )}
                          {task.column !== 'completed' && (
                            <button 
                              onClick={() => moveTask(task.id, 'next')}
                              className="px-1.5 py-0.5 bg-purple-900/60 hover:bg-purple-800 text-purple-200 rounded"
                              title="Avanzar etapa"
                            >
                              ▶
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
