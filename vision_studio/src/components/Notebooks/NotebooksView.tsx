import React, { useState, useEffect, useRef } from 'react';
import { 
  BookOpen, Plus, Trash2, Upload, FileText, Sparkles, 
  Send, HelpCircle, FileCheck, Mic, Loader2, AlertCircle, Search, Compass, RefreshCw, Globe
} from 'lucide-react';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { apiErrorMessage, splitChatStream } from '../../lib/notebookApi';


interface Source {
  id: string;
  filename: string;
  description?: string;
  added_at: string;
  status: 'ready' | 'processing' | 'error';
  chunks: number;
}

interface Note {
  id: string;
  title: string;
  type: string;
  content: string;
  created_at: string;
}

interface Notebook {
  id: string;
  title: string;
  description: string;
  created_at: string;
  sources_count: number;
  notes_count: number;
  sources: Source[];
  notes: Note[];
  research?: { status: 'running' | 'done' | 'error'; error: string | null } | null;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  error?: string;
}

export default function NotebooksView() {
  const settings = useSettingsStore();
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [activeNotebookId, setActiveNotebookId] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  // Auto-Research State
  const [isResearchModalOpen, setIsResearchModalOpen] = useState(false);
  const [researchTopic, setResearchTopic] = useState('');
  const [isResearching, setIsResearching] = useState(false);

  // Active Notebook State
  const [activeTab, setActiveTab] = useState<'sources' | 'synthesis' | 'chat'>('sources');
  const [isUploading, setIsUploading] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [synthesisError, setSynthesisError] = useState<string | null>(null);
  const [researchingNotebookIds, setResearchingNotebookIds] = useState<string[]>([]);

  // Chat State & Controls
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isChatStreaming, setIsChatStreaming] = useState(false);
  const [searchWeb, setSearchWeb] = useState(false);
  const [searchMode, setSearchMode] = useState<'simple' | 'profundo'>('simple');
  const [maxWebResults, setMaxWebResults] = useState<number>(5);
  const [responseStyle, setResponseStyle] = useState<'conciso' | 'abierto'>('conciso');
  const chatEndRef = useRef<HTMLDivElement>(null);

  const activeNotebook = notebooks.find(n => n.id === activeNotebookId) || null;

  useEffect(() => {
    fetchNotebooks();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const fetchNotebooks = async (): Promise<Notebook[]> => {
    setIsLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/cuadernos');
      const data = await res.json();
      if (data.status === 'success') {
        setNotebooks(data.cuadernos);
        if (data.cuadernos.length > 0 && !activeNotebookId) {
          setActiveNotebookId(data.cuadernos[0].id);
        }
        return data.cuadernos;
      }
    } catch (err) {
      console.error('Error fetching notebooks:', err);
    } finally {
      setIsLoading(false);
    }
    return [];
  };

  const handleCreateNotebook = async () => {
    if (!newTitle.trim()) return;
    try {
      const res = await fetch('http://127.0.0.1:8000/api/cuadernos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle, description: 'Cuaderno de estudio' })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setNewTitle('');
        setIsCreating(false);
        await fetchNotebooks();
        setActiveNotebookId(data.cuaderno.id);
      }
    } catch (err) {
      console.error('Error creating notebook:', err);
    }
  };

  const handleAutoResearch = async () => {
    if (!researchTopic.trim() || isResearching) return;
    setIsResearching(true);
    const apiKey = settings.apiKeys['openrouter'] || '';

    try {
      const res = await fetch('http://127.0.0.1:8000/api/cuadernos/investigar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tema: researchTopic, api_key: apiKey })
      });
      const data = await res.json();
      if (data.status === 'success' && data.cuaderno) {
        const newId = data.cuaderno.id;
        setResearchTopic('');
        setIsResearchModalOpen(false);
        setResearchingNotebookIds(prev => [...prev, newId]);

        await fetchNotebooks();
        setActiveNotebookId(newId);

        // Poll every 3 seconds until research (sources + syntheses) finishes
        let count = 0;
        const interval = setInterval(async () => {
          count++;
          const currentList = await fetchNotebooks();
          const targetNb = currentList.find(n => n.id === newId);
          const isDone = (targetNb && targetNb.research?.status !== 'running') || count >= 10;
          if (isDone) {
            setResearchingNotebookIds(prev => prev.filter(id => id !== newId));
            clearInterval(interval);
          }
        }, 3000);
      }
    } catch (err) {
      console.error('Error auto researching notebook:', err);
    } finally {
      setIsResearching(false);
    }
  };

  const handleDeleteNotebook = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('¿Seguro que deseas eliminar este cuaderno y sus fuentes?')) return;
    try {
      await fetch(`http://127.0.0.1:8000/api/cuadernos/${id}`, { method: 'DELETE' });
      await fetchNotebooks();
      if (activeNotebookId === id) {
        setActiveNotebookId(null);
      }
    } catch (err) {
      console.error('Error deleting notebook:', err);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!activeNotebookId || !e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    setIsUploading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/cuadernos/${activeNotebookId}/fuentes`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.status === 'success') {
        await fetchNotebooks();
        setTimeout(fetchNotebooks, 3000);
      }
    } catch (err) {
      console.error('Error uploading file source:', err);
    } finally {
      setIsUploading(false);
    }
  };

  const handleGenerateSynthesis = async (tipo: string) => {
    if (!activeNotebookId) return;
    setIsSynthesizing(true);
    setSynthesisError(null);
    const apiKey = settings.apiKeys['openrouter'] || '';

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/cuadernos/${activeNotebookId}/sintesis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tipo, api_key: apiKey })
      });
      const data = await res.json().catch(() => null);
      if (data?.status === 'success') {
        await fetchNotebooks();
      } else {
        setSynthesisError(apiErrorMessage(data, `Error ${res.status} al generar la síntesis.`));
      }
    } catch (err) {
      console.error('Error generating synthesis:', err);
      setSynthesisError('No se pudo conectar con el gateway.');
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handleSendChat = async (customQuery?: string, forcedMode?: 'simple' | 'profundo') => {
    const queryText = customQuery !== undefined ? customQuery : chatInput;
    if (!queryText.trim() || !activeNotebookId || isChatStreaming) return;
    
    const activeSearchMode = forcedMode || searchMode;
    const effectiveMaxResults = activeSearchMode === 'profundo' ? Math.max(maxWebResults, 25) : maxWebResults;
    const isWebSearch = searchWeb || activeSearchMode === 'profundo' || queryText.startsWith('@web');

    if (customQuery === undefined) {
      setChatInput('');
    }
    setChatMessages(prev => [...prev, { role: 'user', text: queryText }]);
    setIsChatStreaming(true);

    const apiKey = settings.apiKeys['openrouter'] || '';
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/cuadernos/${activeNotebookId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryText,
          history: chatMessages.filter(m => !m.error),
          api_key: apiKey,
          search_web: isWebSearch,
          search_mode: activeSearchMode,
          max_web_results: effectiveMaxResults,
          response_style: responseStyle
        })
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const error = apiErrorMessage(data, `Error ${res.status} del gateway.`);
        setChatMessages(prev => [...prev, { role: 'assistant', text: '', error }]);
        return;
      }
      if (!res.body) throw new Error('No readable stream');
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistantText = '';

      setChatMessages(prev => [...prev, { role: 'assistant', text: '' }]);

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        assistantText += chunk;
        const { answer, error } = splitChatStream(assistantText);

        setChatMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = { role: 'assistant', text: answer, error: error ?? undefined };
          return updated;
        });
      }
    } catch (err) {
      console.error('Error streaming notebook chat:', err);
      setChatMessages(prev => [...prev, { role: 'assistant', text: '', error: 'Error al conectar con la fuente del cuaderno.' }]);
    } finally {
      setIsChatStreaming(false);
      if (isWebSearch) {
        fetchNotebooks();
      }
    }
  };

  const isNotebookProcessing = (nb: Notebook) => {
    return (
      researchingNotebookIds.includes(nb.id) ||
      nb.sources.some(s => s.status === 'processing') ||
      nb.research?.status === 'running'
    );
  };


  return (
    <div className="flex h-full w-full bg-[#1e1e1f] text-[#cccccc] font-sans overflow-hidden">
      {/* Sidebar: Lista de Cuadernos */}
      <div className="w-64 border-r border-[#3c3c3c] bg-[#252526] flex flex-col flex-shrink-0">
        <div className="p-3 border-b border-[#3c3c3c] flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5 text-[#a78bfa]">
            <BookOpen size={14} /> Mis Cuadernos
            {isLoading && <Loader2 size={12} className="animate-spin text-[#a78bfa]" />}
          </span>
          <div className="flex items-center gap-1">
            <button 
              onClick={() => { fetchNotebooks(); }}
              className="p-1 hover:bg-[#3c3c3c] rounded text-gray-400 hover:text-white transition-colors"
              title="Refrescar Cuadernos"
            >
              <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            </button>
            <button 
              onClick={() => { setIsResearchModalOpen(prev => !prev); setIsCreating(false); }}
              className="p-1 hover:bg-[#3c3c3c] rounded text-amber-400 transition-colors"
              title="Auto-Investigar con IA"
            >
              <Compass size={16} />
            </button>
            <button 
              onClick={() => { setIsCreating(prev => !prev); setIsResearchModalOpen(false); }}
              className="p-1 hover:bg-[#3c3c3c] rounded text-[#a78bfa] transition-colors"
              title="Nuevo Cuaderno Manual"
            >
              <Plus size={16} />
            </button>
          </div>
        </div>

        {/* Modal / Form de Auto-Investigación */}
        {isResearchModalOpen && (
          <div className="p-3 border-b border-[#3c3c3c] bg-[#1e1e1f] space-y-2 animate-fadeIn">
            <span className="text-[11px] font-semibold text-amber-300 flex items-center gap-1">
              <Sparkles size={12} /> Auto-Investigación por IA
            </span>
            <input 
              type="text" 
              placeholder="Ingresá el tema (ej. Física Cuántica)..." 
              value={researchTopic}
              onChange={e => setResearchTopic(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAutoResearch()}
              disabled={isResearching}
              className="w-full bg-[#2d2d2d] border border-[#3c3c3c] rounded text-xs px-2 py-1 outline-none focus:border-amber-400 text-white"
            />
            <div className="flex justify-end gap-1">
              <button 
                onClick={() => setIsResearchModalOpen(false)} 
                disabled={isResearching}
                className="text-[10px] px-2 py-0.5 text-gray-400 hover:text-white"
              >
                Cancelar
              </button>
              <button 
                onClick={handleAutoResearch} 
                disabled={isResearching || !researchTopic.trim()}
                className="text-[10px] px-2 py-0.5 bg-amber-500 hover:bg-amber-600 text-black font-semibold rounded flex items-center gap-1 disabled:opacity-50"
              >
                {isResearching ? <Loader2 size={10} className="animate-spin" /> : <Search size={10} />} Investigar
              </button>
            </div>
          </div>
        )}

        {isCreating && (
          <div className="p-2 border-b border-[#3c3c3c] bg-[#1e1e1f] space-y-2 animate-fadeIn">
            <input 
              type="text" 
              placeholder="Título del cuaderno..." 
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreateNotebook()}
              className="w-full bg-[#2d2d2d] border border-[#3c3c3c] rounded text-xs px-2 py-1 outline-none focus:border-[#7c6ff0]"
            />
            <div className="flex justify-end gap-1">
              <button onClick={() => setIsCreating(false)} className="text-[10px] px-2 py-0.5 text-gray-400 hover:text-white">Cancelar</button>
              <button onClick={handleCreateNotebook} className="text-[10px] px-2 py-0.5 bg-[#7c6ff0] text-white rounded font-medium">Crear</button>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto custom-scrollbar p-1 space-y-1">
          {notebooks.length === 0 && !isLoading && (
            <div className="p-4 text-center text-xs text-gray-500">
              No hay cuadernos creados. Hacé clic en + o en la brújula para auto-investigar un tema.
            </div>
          )}

          {notebooks.map(nb => {
            const processing = isNotebookProcessing(nb);
            return (
              <div 
                key={nb.id}
                onClick={() => { setActiveNotebookId(nb.id); setChatMessages([]); setSynthesisError(null); }}
                className={`group flex items-center justify-between p-2.5 rounded-lg cursor-pointer text-xs transition-colors ${
                  activeNotebookId === nb.id ? 'bg-[#37373d] text-white border-l-2 border-[#7c6ff0]' : 'hover:bg-[#2a2d2e]'
                }`}
              >
                <div className="flex flex-col min-w-0 pr-2">
                  <span className="font-medium truncate flex items-center gap-1">
                    {processing ? (
                      <Loader2 size={11} className="animate-spin text-amber-400 flex-shrink-0" />
                    ) : nb.title.startsWith('Investigación:') ? (
                      <Sparkles size={11} className="text-amber-400 flex-shrink-0" />
                    ) : null}
                    {nb.title}
                  </span>
                  <span className="text-[10px] text-gray-400 flex items-center gap-1">
                    {processing ? (
                      <span className="text-amber-300 font-mono animate-pulse">Investigando...</span>
                    ) : nb.research?.status === 'error' ? (
                      <span className="text-red-400">Investigación fallida</span>
                    ) : (
                      <>{nb.sources_count} fuentes · {nb.notes_count} notas</>
                    )}
                  </span>
                </div>
                <button 
                  onClick={(e) => handleDeleteNotebook(nb.id, e)}
                  className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-400 p-1 transition-opacity"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Workspace */}
      {activeNotebook ? (
        <div className="flex-1 flex flex-col h-full bg-[#1e1e1f] overflow-hidden">
          {/* Header */}
          <div className="p-3 border-b border-[#3c3c3c] bg-[#252526] flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <BookOpen size={16} className="text-[#a78bfa]" /> {activeNotebook.title}
                {isNotebookProcessing(activeNotebook) && (
                  <span className="text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full font-mono flex items-center gap-1 animate-pulse">
                    <Loader2 size={10} className="animate-spin" /> PROCESANDO
                  </span>
                )}
              </h2>
              <p className="text-[11px] text-gray-400">{activeNotebook.description || 'Sin descripción'}</p>
            </div>

            {/* Navigation Tabs */}
            <div className="flex items-center bg-[#1e1e1f] p-0.5 rounded-lg border border-[#3c3c3c] text-xs">
              <button 
                onClick={() => setActiveTab('sources')}
                className={`px-3 py-1 rounded-md flex items-center gap-1 transition-all ${
                  activeTab === 'sources' ? 'bg-[#7c6ff0] text-white font-medium' : 'text-gray-400 hover:text-white'
                }`}
              >
                <FileText size={13} /> Fuentes ({activeNotebook.sources.length})
              </button>
              <button 
                onClick={() => setActiveTab('synthesis')}
                className={`px-3 py-1 rounded-md flex items-center gap-1 transition-all ${
                  activeTab === 'synthesis' ? 'bg-[#7c6ff0] text-white font-medium' : 'text-gray-400 hover:text-white'
                }`}
              >
                <Sparkles size={13} /> Síntesis ({activeNotebook.notes.length})
              </button>
              <button 
                onClick={() => setActiveTab('chat')}
                className={`px-3 py-1 rounded-md flex items-center gap-1 transition-all ${
                  activeTab === 'chat' ? 'bg-[#7c6ff0] text-white font-medium' : 'text-gray-400 hover:text-white'
                }`}
              >
                <Send size={13} /> Chat Acotado
              </button>
            </div>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-hidden relative p-4">
            {/* Tab Fuentes */}
            {activeTab === 'sources' && (
              <div className="h-full flex flex-col space-y-4 max-w-4xl mx-auto">
                {/* Upload Banner */}
                <label className="border-2 border-dashed border-[#3c3c3c] hover:border-[#7c6ff0] bg-[#252526]/50 rounded-xl p-6 text-center cursor-pointer transition-colors flex flex-col items-center justify-center gap-2 relative overflow-hidden">
                  <input type="file" onChange={handleFileUpload} accept=".pdf,.txt,.csv,.md" className="hidden" />
                  {isUploading ? (
                    <div className="flex flex-col items-center gap-2 text-[#7c6ff0] animate-pulse">
                      <Loader2 size={32} className="animate-spin" />
                      <span className="text-xs font-semibold">Procesando e indexando documento en LanceDB...</span>
                    </div>
                  ) : (
                    <>
                      <Upload size={28} className="text-[#a78bfa]" />
                      <span className="text-xs font-semibold text-white">Cargar Fuente Manual (PDF, TXT, CSV, MD)</span>
                      <span className="text-[10px] text-gray-400">Arrastrá un archivo o hacé clic para seleccionar. Las fuentes se procesan con PyPDFLoader e indexan en LanceDB.</span>
                    </>
                  )}
                </label>

                {/* Auto Research Active Processing Banner */}
                {isNotebookProcessing(activeNotebook) && (
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex items-center gap-3 text-xs text-amber-300 animate-pulse">
                    <Loader2 size={24} className="animate-spin text-amber-400 flex-shrink-0" />
                    <div>
                      <span className="font-semibold block">Investigación Autónoma en Curso por IA</span>
                      <span className="text-[10px] text-gray-300 block">El agente está consultando la web, sanitizando el texto extraído e indexándolo en LanceDB. Las fuentes y las notas de síntesis aparecerán aquí automáticamente en unos segundos...</span>
                    </div>
                  </div>
                )}

                {activeNotebook.research?.status === 'error' && (
                  <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3 text-xs text-red-300">
                    <AlertCircle size={24} className="text-red-400 flex-shrink-0" />
                    <div>
                      <span className="font-semibold block">La investigación autónoma falló</span>
                      <span className="text-[10px] text-gray-300 block">{activeNotebook.research.error}</span>
                    </div>
                  </div>
                )}

                {/* Sources List */}
                <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2">
                      Fuentes Adjuntas
                      {isLoading && <Loader2 size={11} className="animate-spin text-gray-400" />}
                    </h3>
                    <button 
                      onClick={fetchNotebooks} 
                      className="text-[10px] text-[#a78bfa] hover:underline flex items-center gap-1"
                    >
                      <RefreshCw size={10} className={isLoading ? 'animate-spin' : ''} /> Actualizar
                    </button>
                  </div>

                  {activeNotebook.sources.length === 0 ? (
                    <div className="text-xs text-gray-500 italic p-6 text-center bg-[#252526]/30 rounded-xl border border-[#3c3c3c]/50 space-y-2">
                      <p>No hay fuentes en este cuaderno aún.</p>
                    </div>
                  ) : (
                    activeNotebook.sources.map(src => (
                      <div key={src.id} className="bg-[#252526] p-3 rounded-lg border border-[#3c3c3c] flex items-center justify-between text-xs">
                        <div className="flex items-center gap-3">
                          <FileText size={18} className="text-[#a78bfa]" />
                          <div>
                            <span className="font-semibold text-white block">{src.filename}</span>
                            <span className="text-[10px] text-gray-400">{src.chunks} fragmentos indexados</span>
                          </div>
                        </div>

                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono flex items-center gap-1 ${
                          src.status === 'ready' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' :
                          src.status === 'processing' ? 'bg-amber-500/20 text-amber-300 animate-pulse border border-amber-500/30' :
                          'bg-red-500/20 text-red-300 border border-red-500/30'
                        }`}>
                          {src.status === 'ready' && <FileCheck size={10} />}
                          {src.status === 'processing' && <Loader2 size={10} className="animate-spin" />}
                          {src.status === 'error' && <AlertCircle size={10} />}
                          {src.status.toUpperCase()}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Tab Síntesis */}
            {activeTab === 'synthesis' && (
              <div className="h-full flex flex-col space-y-4 max-w-4xl mx-auto overflow-y-auto custom-scrollbar">
                {/* Generation Buttons */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <button 
                    onClick={() => handleGenerateSynthesis('resumen')}
                    disabled={isSynthesizing}
                    className="p-3 bg-[#252526] hover:bg-[#2a2d2e] border border-[#3c3c3c] rounded-xl text-left transition-all flex flex-col gap-1.5 disabled:opacity-50"
                  >
                    <Sparkles size={16} className="text-purple-400" />
                    <span className="text-xs font-semibold text-white">Resumen Exec</span>
                    <span className="text-[10px] text-gray-400">Puntos clave y visión general</span>
                  </button>

                  <button 
                    onClick={() => handleGenerateSynthesis('guia_estudio')}
                    disabled={isSynthesizing}
                    className="p-3 bg-[#252526] hover:bg-[#2a2d2e] border border-[#3c3c3c] rounded-xl text-left transition-all flex flex-col gap-1.5 disabled:opacity-50"
                  >
                    <BookOpen size={16} className="text-blue-400" />
                    <span className="text-xs font-semibold text-white">Guía de Estudio</span>
                    <span className="text-[10px] text-gray-400">Glosario y conceptos centrales</span>
                  </button>

                  <button 
                    onClick={() => handleGenerateSynthesis('faq')}
                    disabled={isSynthesizing}
                    className="p-3 bg-[#252526] hover:bg-[#2a2d2e] border border-[#3c3c3c] rounded-xl text-left transition-all flex flex-col gap-1.5 disabled:opacity-50"
                  >
                    <HelpCircle size={16} className="text-emerald-400" />
                    <span className="text-xs font-semibold text-white">Preguntas FAQ</span>
                    <span className="text-[10px] text-gray-400">Preguntas y respuestas clave</span>
                  </button>

                  <button 
                    onClick={() => handleGenerateSynthesis('podcast_script')}
                    disabled={isSynthesizing}
                    className="p-3 bg-[#252526] hover:bg-[#2a2d2e] border border-[#3c3c3c] rounded-xl text-left transition-all flex flex-col gap-1.5 disabled:opacity-50"
                  >
                    <Mic size={16} className="text-amber-400" />
                    <span className="text-xs font-semibold text-white">Guion Podcast</span>
                    <span className="text-[10px] text-gray-400">Diálogo de debate (Audio Overview)</span>
                  </button>
                </div>

                {isSynthesizing && (
                  <div className="p-4 bg-purple-500/10 border border-purple-500/30 rounded-xl flex items-center justify-center gap-2 text-xs text-purple-300 font-medium animate-pulse">
                    <Loader2 size={18} className="animate-spin text-purple-400" /> El Sintetizador Cognitivo está analizando las fuentes y generando la nota...
                  </div>
                )}

                {synthesisError && (
                  <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl flex items-center gap-2 text-xs text-red-300">
                    <AlertCircle size={18} className="text-red-400 flex-shrink-0" /> {synthesisError}
                  </div>
                )}

                {/* Synthesized Notes List */}
                <div className="space-y-3 pt-2">
                  {activeNotebook.notes.length === 0 ? (
                    <div className="text-xs text-gray-500 italic p-6 text-center bg-[#252526]/30 rounded-xl border border-[#3c3c3c]/50">
                      Aún no generaste notas de síntesis. Seleccioná una de las opciones arriba para crear un resumen automático.
                    </div>
                  ) : (
                    activeNotebook.notes.map(note => (
                      <div key={note.id} className="bg-[#252526] p-4 rounded-xl border border-[#3c3c3c] space-y-2">
                        <div className="flex items-center justify-between border-b border-[#3c3c3c] pb-2">
                          <span className="font-semibold text-xs text-white">{note.title}</span>
                          <span className="text-[10px] text-gray-400">{new Date(note.created_at).toLocaleTimeString()}</span>
                        </div>
                        <div className="text-xs leading-relaxed text-gray-300 whitespace-pre-wrap font-sans">
                          {note.content}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Tab Chat Grounded */}
            {activeTab === 'chat' && (
              <div className="h-full flex flex-col max-w-4xl mx-auto bg-[#252526] rounded-xl border border-[#3c3c3c] overflow-hidden">
                {/* Messages Box */}
                <div className="flex-1 p-4 overflow-y-auto custom-scrollbar space-y-3">
                  {chatMessages.length === 0 && (
                    <div className="text-center p-8 text-xs text-gray-500 space-y-2">
                      <BookOpen size={32} className="mx-auto text-[#a78bfa] opacity-60" />
                      <p className="font-semibold text-gray-300">Chat Acotado a este Cuaderno</p>
                      <p className="max-w-md mx-auto text-[11px]">
                        El agente responderá únicamente utilizando la información contenida en las fuentes de este cuaderno. Si la respuesta no figura en las fuentes, te lo indicará explícitamente.
                      </p>
                    </div>
                  )}

                  {chatMessages.map((msg, idx) => (
                    <div 
                      key={idx} 
                      className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                    >
                      <div className={`max-w-[80%] p-3 rounded-xl text-xs whitespace-pre-wrap leading-relaxed ${
                        msg.role === 'user' 
                          ? 'bg-[#7c6ff0] text-white rounded-br-none' 
                          : 'bg-[#1e1e1f] text-gray-200 border border-[#3c3c3c] rounded-bl-none font-sans'
                      }`}>
                        {msg.text || (isChatStreaming && idx === chatMessages.length - 1 && !msg.error ? (
                          <span className="flex items-center gap-1 text-[#a78bfa]">
                            <Loader2 size={12} className="animate-spin" /> Escribiendo respuesta basada en fuentes...
                          </span>
                        ) : '')}
                        {msg.error && (
                          <span className={`flex items-center gap-1 text-red-300 ${msg.text ? 'mt-2' : ''}`}>
                            <AlertCircle size={12} className="flex-shrink-0" /> {msg.error}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </div>

                {/* Config Controls Toolbar */}
                <div className="px-3 py-2 border-t border-[#3c3c3c] bg-[#181819] flex items-center justify-between gap-2 text-xs flex-wrap">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider">Búsqueda Web:</span>
                    
                    <button
                      onClick={() => { 
                        setSearchMode('simple'); 
                        setSearchWeb(prev => searchMode === 'simple' ? !prev : true); 
                      }}
                      className={`px-2.5 py-1 rounded-lg border text-[11px] font-medium flex items-center gap-1.5 transition-all ${
                        searchWeb && searchMode === 'simple'
                          ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-sm' 
                          : 'bg-[#252526] text-gray-400 border-[#3c3c3c] hover:text-gray-200'
                      }`}
                      title="Búsqueda rápida en la web (5 fuentes)"
                    >
                      <Globe size={13} className={searchWeb && searchMode === 'simple' ? 'text-amber-400' : ''} />
                      Simple (5 fuentes)
                    </button>

                    <button
                      onClick={() => { 
                        setSearchMode('profundo'); 
                        setSearchWeb(true); 
                      }}
                      className={`px-2.5 py-1 rounded-lg border text-[11px] font-medium flex items-center gap-1.5 transition-all ${
                        searchWeb && searchMode === 'profundo'
                          ? 'bg-purple-500/25 text-purple-300 border-purple-500/60 shadow-md shadow-purple-900/30 ring-1 ring-purple-500/30' 
                          : 'bg-[#252526] text-gray-400 border-[#3c3c3c] hover:text-purple-300'
                      }`}
                      title="Búsqueda profunda exhaustiva (>20 fuentes: foros, webs, vídeos, datos) y generación de informe con citas"
                    >
                      <Sparkles size={13} className={searchWeb && searchMode === 'profundo' ? 'text-purple-400 animate-pulse' : ''} />
                      Profunda (&gt;20 fuentes)
                    </button>

                    {searchWeb && searchMode === 'simple' && (
                      <div className="flex items-center gap-1 bg-[#252526] px-2 py-0.5 rounded-lg border border-[#3c3c3c]">
                        <span className="text-[10px] text-gray-400">Fuentes:</span>
                        <select
                          value={maxWebResults}
                          onChange={e => setMaxWebResults(Number(e.target.value))}
                          className="bg-transparent text-white text-[11px] outline-none cursor-pointer"
                        >
                          <option value={3} className="bg-[#252526]">3 resultados</option>
                          <option value={5} className="bg-[#252526]">5 resultados</option>
                          <option value={8} className="bg-[#252526]">8 resultados</option>
                          <option value={10} className="bg-[#252526]">10 resultados</option>
                        </select>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-1 bg-[#252526] px-2 py-0.5 rounded-lg border border-[#3c3c3c]">
                    <span className="text-[10px] text-gray-400">Estilo:</span>
                    <button
                      onClick={() => setResponseStyle('conciso')}
                      className={`text-[10px] px-2 py-0.5 rounded font-medium transition-colors ${
                        responseStyle === 'conciso' ? 'bg-[#7c6ff0] text-white' : 'text-gray-400 hover:text-white'
                      }`}
                    >
                      Conciso
                    </button>
                    <button
                      onClick={() => setResponseStyle('abierto')}
                      className={`text-[10px] px-2 py-0.5 rounded font-medium transition-colors ${
                        responseStyle === 'abierto' ? 'bg-[#7c6ff0] text-white' : 'text-gray-400 hover:text-white'
                      }`}
                    >
                      Abierto
                    </button>
                  </div>
                </div>

                {/* Quick Action Button for Contextual Deep Search */}
                <div className="px-3 py-1.5 bg-[#181819] border-t border-[#3c3c3c]/60 flex items-center justify-between gap-2">
                  <button
                    onClick={() => {
                      const targetText = chatInput.trim() || (chatMessages.length > 0 ? chatMessages[chatMessages.length - 1].text : '');
                      if (!targetText) return;
                      handleSendChat(`Buscá información profunda al respecto de: ${targetText}`, 'profundo');
                    }}
                    disabled={isChatStreaming}
                    className="w-full py-1.5 px-3 bg-gradient-to-r from-purple-950/60 via-indigo-950/60 to-slate-900/80 hover:from-purple-900/80 hover:to-indigo-900/80 border border-purple-500/40 hover:border-purple-400 rounded-lg text-xs text-purple-200 font-medium flex items-center justify-center gap-2 transition-all shadow-sm disabled:opacity-40"
                    title="Realiza una búsqueda profunda (+20 fuentes) sobre la entrada o la conversación actual y genera una nota con el informe de citas"
                  >
                    <Sparkles size={13} className="text-amber-300 animate-pulse" />
                    <span>Buscá información profunda al respecto de este dato</span>
                    <span className="text-[9px] bg-purple-500/30 px-1.5 py-0.5 rounded text-purple-200 font-mono uppercase tracking-wider">+20 fuentes & citas</span>
                  </button>
                </div>

                {/* Input Area */}
                <div className="p-3 border-t border-[#3c3c3c] bg-[#1e1e1f] flex items-center gap-2">
                  <input 
                    type="text" 
                    placeholder={
                      searchMode === 'profundo'
                        ? "Escribí el tema o consulta para búsqueda profunda (>20 fuentes + Informe con citas)..."
                        : searchWeb 
                        ? "Escribí tu pregunta para buscar e indexar rápido en la web..." 
                        : "Hacé una pregunta sobre las fuentes de este cuaderno..."
                    }
                    value={chatInput}
                    onChange={e => setChatInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSendChat()}
                    disabled={isChatStreaming}
                    className="flex-1 bg-[#252526] border border-[#3c3c3c] focus:border-[#7c6ff0] rounded-xl px-3 py-2 text-xs text-white outline-none"
                  />
                  <button 
                    onClick={() => handleSendChat()}
                    disabled={isChatStreaming || !chatInput.trim()}
                    className="p-2 bg-[#7c6ff0] hover:bg-[#6366f1] text-white rounded-xl disabled:opacity-40 transition-colors"
                  >
                    {isChatStreaming ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                  </button>
                </div>

              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-center p-8 text-gray-500 text-xs">
          Seleccioná un cuaderno de la barra lateral o hacé clic en la brújula para auto-investigar un tema.
        </div>
      )}
    </div>
  );
}
