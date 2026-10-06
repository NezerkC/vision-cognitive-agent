import React, { useState } from 'react';
import { Folder, FileText, Search, X, Check, HardDrive } from 'lucide-react';

interface FilePickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
  title: string;
  mode: 'folder' | 'file';
  initialPath?: string;
  fileExtension?: string;
}

export default function FilePickerModal({
  isOpen,
  onClose,
  onSelect,
  title,
  mode,
  initialPath = 'C:\\Users\\lolpl\\Desktop\\llama.cpp',
  fileExtension = '.gguf'
}: FilePickerModalProps) {
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [quickPaths] = useState([
    'C:\\Users\\lolpl\\Desktop\\llama.cpp\\llama-b10082-bin-win-cuda-13.3-x64',
    'C:\\Users\\lolpl\\Desktop\\llama.cpp\\llama-b10082-bin-win-cuda-13.3-x64\\gguf',
    'C:\\Users\\lolpl\\Desktop\\llama.cpp\\llama-b10082-bin-win-cuda-13.3-x64\\gguf\\qwen3.6-35B-A3B\\Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf'
  ]);

  if (!isOpen) return null;

  const handleNativeFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const fileObj = e.target.files[0];
      // En Tauri/Electron e.target.files[0].path contiene la ruta absoluta completa en el sistema operativo
      const fullPath = (fileObj as any).path || fileObj.name;
      setCurrentPath(fullPath);
    }
  };

  const handleConfirm = () => {
    if (currentPath) {
      onSelect(currentPath);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#252526] border border-[#3c3c3c] rounded-xl w-[520px] shadow-2xl overflow-hidden flex flex-col text-xs text-[#cccccc]">
        
        {/* Header */}
        <div className="flex justify-between items-center px-4 py-3 bg-[#1e1e1e] border-b border-[#3c3c3c]">
          <h3 className="font-semibold text-white flex items-center gap-2">
            {mode === 'folder' ? <Folder size={16} className="text-[#a78bfa]" /> : <FileText size={16} className="text-emerald-400" />}
            {title}
          </h3>
          <button onClick={onClose} className="text-[#8a8a8a] hover:text-white transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-4">
          
          {/* Opción 1: Abrir Selector Nativo del Sistema Operativo */}
          <div className="bg-[#1e1e1e] p-3 rounded-lg border border-[#3c3c3c] space-y-2">
            <span className="font-medium text-white block text-[11px]">
              1. Selector Nativo de Explorador de Windows:
            </span>
            <label className="flex items-center justify-center gap-2 bg-[#3c3c3c] hover:bg-[#4c4c4c] text-white py-2 px-4 rounded cursor-pointer transition-colors font-semibold">
              <Search size={14} />
              {mode === 'file' ? `Buscar archivo ${fileExtension} en Windows...` : 'Buscar carpeta en Windows...'}
              <input 
                type="file" 
                accept={mode === 'file' ? fileExtension : undefined}
                onChange={handleNativeFileChange}
                className="hidden"
              />
            </label>
          </div>

          {/* Opción 2: Entrada Manual / Editar Ruta */}
          <div className="space-y-1.5">
            <label className="font-medium text-[#cccccc] block text-[11px]">
              2. Ruta Completa Seleccionada:
            </label>
            <input 
              type="text" 
              value={currentPath}
              onChange={(e) => setCurrentPath(e.target.value)}
              placeholder="C:\Ruta\al\archivo_o_carpeta"
              className="w-full bg-[#1e1e1e] border border-[#3c3c3c] text-white px-3 py-2 rounded outline-none focus:border-[#a78bfa] font-mono text-[11px]"
            />
          </div>

          {/* Accesos Rápidos detectados */}
          <div className="space-y-2 pt-1 border-t border-[#3c3c3c]">
            <span className="font-semibold text-[#8a8a8a] text-[10px] uppercase tracking-wider block">
              Rutas y Accesos Rápidos Recomendados:
            </span>
            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
              {quickPaths.map((path, idx) => (
                <div 
                  key={idx}
                  onClick={() => setCurrentPath(path)}
                  className={`p-2 rounded border cursor-pointer flex items-center gap-2 transition-colors font-mono text-[10px] ${
                    currentPath === path 
                      ? 'bg-[#3b2d54] border-[#a78bfa] text-white' 
                      : 'bg-[#1e1e1e] border-[#3c3c3c] text-[#cccccc] hover:bg-[#2e2e30]'
                  }`}
                >
                  <HardDrive size={13} className="text-[#a78bfa] flex-shrink-0" />
                  <span className="truncate flex-1">{path}</span>
                  {currentPath === path && <Check size={13} className="text-emerald-400" />}
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-4 py-3 bg-[#1e1e1e] border-t border-[#3c3c3c]">
          <button 
            onClick={onClose}
            className="px-4 py-1.5 rounded border border-[#3c3c3c] text-[#cccccc] hover:bg-[#3c3c3c] transition-colors"
          >
            Cancelar
          </button>
          <button 
            onClick={handleConfirm}
            className="px-5 py-1.5 rounded bg-[#7c6ff0] hover:bg-[#a78bfa] text-white font-semibold flex items-center gap-1.5 transition-colors"
          >
            <Check size={14} />
            Seleccionar
          </button>
        </div>

      </div>
    </div>
  );
}
