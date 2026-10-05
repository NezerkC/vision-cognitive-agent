import { useEffect } from 'react';
import { useNotificationStore, ToastMessage } from '../../stores/useNotificationStore';
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';

const ToastItem = ({ toast }: { toast: ToastMessage }) => {
  const removeToast = useNotificationStore((state) => state.removeToast);

  useEffect(() => {
    const timer = setTimeout(() => {
      removeToast(toast.id);
    }, toast.duration || 4000);
    return () => clearTimeout(timer);
  }, [toast, removeToast]);

  const getBorderColor = () => {
    switch (toast.type) {
      case 'success': return 'border-emerald-500 bg-[#1e2a22] text-emerald-300';
      case 'error': return 'border-red-500 bg-[#2b1b1b] text-red-300';
      case 'warning': return 'border-amber-500 bg-[#2b251b] text-amber-300';
      case 'info': default: return 'border-purple-500 bg-[#231b2b] text-purple-300';
    }
  };

  const getIcon = () => {
    switch (toast.type) {
      case 'success': return <CheckCircle2 size={18} className="text-emerald-400 flex-shrink-0" />;
      case 'error': return <AlertCircle size={18} className="text-red-400 flex-shrink-0" />;
      case 'warning': return <AlertTriangle size={18} className="text-amber-400 flex-shrink-0" />;
      case 'info': default: return <Info size={18} className="text-purple-400 flex-shrink-0" />;
    }
  };

  return (
    <div className={`p-3.5 rounded-lg border shadow-xl flex items-start gap-3 w-80 backdrop-blur-md transition-all duration-300 animate-slide-in ${getBorderColor()}`}>
      {getIcon()}
      <div className="flex-1 text-xs space-y-0.5">
        <h5 className="font-semibold text-white tracking-wide">{toast.title}</h5>
        <p className="text-[#cccccc] text-[11px] leading-relaxed">{toast.message}</p>
      </div>
      <button 
        onClick={() => removeToast(toast.id)} 
        className="text-[#8a8a8a] hover:text-white transition-colors"
      >
        <X size={14} />
      </button>
    </div>
  );
};

export default function ToastContainer() {
  const toasts = useNotificationStore((state) => state.toasts);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-auto">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}
