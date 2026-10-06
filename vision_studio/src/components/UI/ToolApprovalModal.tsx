import { ShieldAlert, Terminal, FileCode, Check, X } from 'lucide-react';

export interface ToolApprovalRequest {
  toolName: string;
  args: any;
  onApprove: () => void;
  onReject: () => void;
}

interface Props {
  request: ToolApprovalRequest | null;
}

export default function ToolApprovalModal({ request }: Props) {
  if (!request) return null;

  const { toolName, args, onApprove, onReject } = request;
  const isWriteFile = toolName === 'write_file';
  const isPowerShell = toolName === 'execute_powershell';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-[#1e1e20] border border-[#3c3c3e] rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden text-xs flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-[#2a2438] to-[#1e1e20] px-5 py-4 border-b border-[#3c3c3e] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
              <ShieldAlert size={20} />
            </div>
            <div>
              <h3 className="font-bold text-sm text-white flex items-center gap-2">
                Solicitud de Permiso del Agente
              </h3>
              <p className="text-[#9a9a9a] text-[11px]">
                El modo Build requiere tu confirmación para realizar la siguiente acción.
              </p>
            </div>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto custom-scrollbar">
          {/* Tool Badge */}
          <div className="flex items-center gap-2 bg-[#252528] px-3 py-2 rounded-lg border border-[#3c3c3e]">
            {isWriteFile ? (
              <FileCode size={16} className="text-[#a78bfa]" />
            ) : isPowerShell ? (
              <Terminal size={16} className="text-emerald-400" />
            ) : (
              <ShieldAlert size={16} className="text-blue-400" />
            )}
            <span className="font-mono text-[#e0e0e0] font-semibold">
              Herramienta: <code className="text-[#a78bfa]">{toolName}</code>
            </span>
          </div>

          {/* Details for Write File */}
          {isWriteFile && (
            <div className="space-y-2">
              <div className="flex flex-col gap-1">
                <span className="text-[#8a8a8a] text-[10px] uppercase font-bold tracking-wider">Ruta del Archivo</span>
                <code className="bg-[#141415] p-2 rounded border border-[#3c3c3e] font-mono text-[#7c6ff0] break-all">
                  {args.path || 'Ruta no especificada'}
                </code>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-[#8a8a8a] text-[10px] uppercase font-bold tracking-wider">Vista Previa del Contenido</span>
                <pre className="bg-[#141415] p-3 rounded-lg border border-[#3c3c3e] font-mono text-[11px] text-[#cccccc] max-h-48 overflow-y-auto overflow-x-auto whitespace-pre-wrap leading-relaxed custom-scrollbar">
                  {args.content}
                </pre>
              </div>
            </div>
          )}

          {/* Details for PowerShell */}
          {isPowerShell && (
            <div className="space-y-2">
              <div className="flex flex-col gap-1">
                <span className="text-[#8a8a8a] text-[10px] uppercase font-bold tracking-wider">Comando PowerShell</span>
                <pre className="bg-[#141415] p-3 rounded-lg border border-[#3c3c3e] font-mono text-emerald-400 font-bold max-h-40 overflow-y-auto overflow-x-auto whitespace-pre-wrap custom-scrollbar">
                  {args.command}
                </pre>
              </div>
              {args.cwd && (
                <div className="flex flex-col gap-1">
                  <span className="text-[#8a8a8a] text-[10px] uppercase font-bold tracking-wider">Directorio de Trabajo (CWD)</span>
                  <code className="bg-[#141415] p-2 rounded border border-[#3c3c3e] font-mono text-[#8a8a8a] break-all">
                    {args.cwd}
                  </code>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Buttons */}
        <div className="bg-[#18181a] px-5 py-3 border-t border-[#3c3c3e] flex items-center justify-end gap-3">
          <button
            onClick={onReject}
            className="px-4 py-2 rounded-xl border border-[#3c3c3e] bg-[#252528] hover:bg-[#2e2e32] text-[#cccccc] font-medium transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <X size={14} className="text-rose-400" />
            Rechazar
          </button>
          <button
            onClick={onApprove}
            className="px-5 py-2 rounded-xl bg-gradient-to-r from-[#7c6ff0] to-[#6366f1] hover:from-[#6c5ce7] hover:to-[#4f46e5] text-white font-semibold transition-all shadow-lg shadow-indigo-500/20 flex items-center gap-1.5 cursor-pointer"
          >
            <Check size={14} />
            Aprobar y Ejecutar
          </button>
        </div>
      </div>
    </div>
  );
}
