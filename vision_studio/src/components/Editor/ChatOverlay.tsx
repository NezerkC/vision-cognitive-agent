import React, { useState, useEffect } from 'react';
import { Terminal, Brain, ChevronDown, ChevronUp } from 'lucide-react';

export default function ChatOverlay() {
  const [isExpanded, setIsExpanded] = useState(true);
  const [thoughts, setThoughts] = useState<string[]>([
    "Analizando contexto del proyecto...",
    "Revisando arquitectura del sistema base...",
    "Cargando ontología inicial..."
  ]);

  // Simular streaming de pensamientos
  useEffect(() => {
    if (!isExpanded) return;
    
    const interval = setInterval(() => {
      const demoThoughts = [
        "Inferencia completada.",
        "Ajustando parámetros heurísticos.",
        "Consultando base de memoria episódica.",
        "Refinando propuesta de código."
      ];
      const nextThought = demoThoughts[Math.floor(Math.random() * demoThoughts.length)];
      setThoughts(prev => [...prev.slice(-4), nextThought]);
    }, 5000);
    
    return () => clearInterval(interval);
  }, [isExpanded]);

  return (
    <div className={`absolute bottom-4 right-4 z-50 bg-[#252526] border border-[#3c3c3c] shadow-lg rounded-md overflow-hidden transition-all duration-300 ${isExpanded ? 'w-80' : 'w-40'}`}>
      <div 
        className="flex items-center justify-between bg-[#2d2d2d] px-3 py-2 cursor-pointer hover:bg-[#333333]"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-emerald-500" />
          <span className="text-xs font-semibold text-gray-200">Visión (LangGraph)</span>
        </div>
        {isExpanded ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronUp size={16} className="text-gray-400" />}
      </div>
      
      {isExpanded && (
        <div className="p-3 max-h-48 overflow-y-auto flex flex-col gap-2">
          {thoughts.map((thought, index) => (
            <div key={index} className="flex gap-2 text-xs text-gray-300">
              <Terminal size={12} className="text-blue-400 mt-0.5 shrink-0" />
              <span>{thought}</span>
            </div>
          ))}
          <div className="flex gap-2 text-xs text-emerald-400 animate-pulse mt-1">
            <span className="font-bold">_</span>
            <span>Pensando...</span>
          </div>
        </div>
      )}
    </div>
  );
}
