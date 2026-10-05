import { MessageSquare, Clock } from 'lucide-react';

export default function ChatHistory() {
  const history = [
    { id: 1, title: 'Análisis de arquitectura', time: '10 min ago' },
    { id: 2, title: 'Refactor de protocolo_intriga', time: '1 hr ago' },
    { id: 3, title: 'Configuración inicial', time: '2 hrs ago' }
  ];

  return (
    <div className="flex flex-col text-sm text-gray-400 mt-6 border-t border-[#3c3c3c] pt-4 flex-1">
      <div className="flex items-center gap-1 mb-2 text-blue-400">
        <Clock size={16} />
        <span className="font-semibold uppercase tracking-wider text-xs ml-1">Historial</span>
      </div>
      
      <div className="flex flex-col gap-1 overflow-y-auto max-h-40">
        {history.map(item => (
          <div key={item.id} className="flex flex-col p-2 rounded cursor-pointer hover:bg-[#2a2d2e] transition-colors group">
            <div className="flex items-center gap-2 text-gray-300 group-hover:text-white">
              <MessageSquare size={14} className="text-gray-500 group-hover:text-blue-400 transition-colors" />
              <span className="truncate text-xs">{item.title}</span>
            </div>
            <span className="text-[10px] text-gray-600 ml-6">{item.time}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
