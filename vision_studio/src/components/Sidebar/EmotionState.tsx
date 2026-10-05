import { useState, useEffect } from 'react';
import { Activity, Zap } from 'lucide-react';

export default function EmotionState() {
  const [emotions, setEmotions] = useState({
    alegria: 0.5,
    confianza: 0.8,
    miedo: 0.1,
    sorpresa: 0.3
  });

  useEffect(() => {
    // Simulación de polling al backend FastAPI
    const interval = setInterval(() => {
      setEmotions(prev => ({
        ...prev,
        alegria: Math.min(1, Math.max(0, prev.alegria + (Math.random() * 0.1 - 0.05))),
        sorpresa: Math.min(1, Math.max(0, prev.sorpresa + (Math.random() * 0.2 - 0.1)))
      }));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col text-sm text-gray-400 mt-6 border-t border-[#3c3c3c] pt-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1 text-emerald-400">
          <Activity size={16} />
          <span className="font-semibold uppercase tracking-wider text-xs ml-1">Estado Emocional</span>
        </div>
        <Zap size={14} className="text-yellow-400 animate-pulse" />
      </div>
      
      <div className="flex flex-col gap-3">
        {Object.entries(emotions).map(([key, value]) => (
          <div key={key} className="flex flex-col gap-1">
            <div className="flex justify-between text-xs">
              <span className="capitalize">{key}</span>
              <span>{Math.round(value * 100)}%</span>
            </div>
            <div className="h-1.5 w-full bg-[#2a2d2e] rounded-full overflow-hidden">
              <div 
                className="h-full bg-emerald-500 transition-all duration-500 ease-out" 
                style={{ width: `${value * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
