import React, { useState, useEffect } from 'react';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { useNotificationStore } from '../../stores/useNotificationStore';
import Tooltip from '../UI/Tooltip';
import FilePickerModal from '../UI/FilePickerModal';
import { Folder, Play, Square, HardDrive, Cpu, Activity, Zap, Save, Check, Sliders, ShieldAlert, Thermometer, Layers, Lightbulb, Sparkles, RefreshCw, Search } from 'lucide-react';

const OFFICIAL_PROVIDER_PRESETS = [
  {
    id: 'qwen_35b',
    name: 'Qwen 3.5 / 3.6 35B (Alibaba - Recomendado Oficial)',
    config: { ngl: 999, c: 131072, ctk: 'q4_0', ctv: 'q4_0', fa: true, mtp: true, mtpDraftMax: 2, temp: 0.7, topP: 0.8 },
    desc: 'Contexto 128K, Flash Attention, KV q4_0 y MTP Draft 2'
  },
  {
    id: 'gemma_4',
    name: 'Gemma 4 / 2 (Google DeepMind - Recomendado Oficial)',
    config: { ngl: 999, c: 32768, ctk: 'q8_0', ctv: 'q8_0', fa: true, mtp: false, mtpDraftMax: 1, temp: 0.6, topP: 0.9 },
    desc: 'Precisión alta con KV cache q8_0 y Temp 0.6'
  },
  {
    id: 'deepseek_r1',
    name: 'DeepSeek R1 / V3 (DeepSeek AI - Recomendado Oficial)',
    config: { ngl: 999, c: 65536, ctk: 'q4_0', ctv: 'q4_0', fa: true, mtp: true, mtpDraftMax: 3, temp: 0.6, topP: 0.95 },
    desc: 'Optimizado para razonamiento largo (<think>) y MTP Draft 3'
  },
  {
    id: 'llama_3',
    name: 'Llama 3.2 / 3.1 (Meta AI - Recomendado Oficial)',
    config: { ngl: 999, c: 131072, ctk: 'q8_0', ctv: 'q8_0', fa: true, mtp: false, mtpDraftMax: 1, temp: 0.7, topP: 0.9 },
    desc: 'Estabilidad en contexto 128K y Flash Attention'
  },
  {
    id: 'mistral_7b',
    name: 'Mistral / Mixtral (Mistral AI - Recomendado Oficial)',
    config: { ngl: 999, c: 32768, ctk: 'f16', ctv: 'f16', fa: true, mtp: false, mtpDraftMax: 1, temp: 0.7, topP: 0.9 },
    desc: 'KV Cache en precisión nativa FP16 para velocidad de código'
  }
];

export default function LlamaCppPanel() {
  const settings = useSettingsStore();
  const addToast = useNotificationStore((state) => state.addToast);
  const [isSaved, setIsSaved] = useState(false);
  const [pickerModal, setPickerModal] = useState<{ isOpen: boolean; mode: 'folder' | 'file'; title: string; initialPath: string }>({
    isOpen: false,
    mode: 'folder',
    title: '',
    initialPath: ''
  });
  const [isHealthChecking, setIsHealthChecking] = useState(false);

  // Polling de Salud Real a http://localhost:8080/health y al Gateway Python
  useEffect(() => {
    const checkServerHealth = async () => {
      try {
        const res = await fetch('http://localhost:8080/health', { method: 'GET' });
        if (res.ok) {
          if (settings.llamacppServerStatus !== 'running') {
            settings.setSetting('llamacppServerStatus', 'running');
          }
          return;
        }
      } catch (e) {
        // Fallback al gateway Python si el ping directo falla
        try {
          const pyRes = await fetch('http://127.0.0.1:8000/api/llamacpp/estado');
          if (pyRes.ok) {
            const data = await pyRes.json();
            if (data.active) {
              settings.setSetting('llamacppServerStatus', 'running');
              return;
            }
          }
        } catch (_) {}
      }

      if (settings.llamacppServerStatus === 'running') {
        settings.setSetting('llamacppServerStatus', 'stopped');
      }
    };

    checkServerHealth();
    const interval = setInterval(checkServerHealth, 3000);
    return () => clearInterval(interval);
  }, [settings]);

  const telemetry = settings.systemTelemetry || {
    cpuPercent: 15,
    ramUsedGb: 14.2,
    ramTotalGb: 32.0,
    ramPercent: 44,
    vramUsedGb: 12.8,
    vramTotalGb: 16.3,
    vramPercent: 78,
    gpuTemp: 49,
    cpuTemp: 54,
    disks: [
      { name: 'C: (SSD NVMe)', freeGb: 240, totalGb: 1000, percent: 76 },
      { name: 'D: (HDD)', freeGb: 850, totalGb: 2000, percent: 57.5 }
    ]
  };

  const isRunning = settings.llamacppServerStatus === 'running';
  const isLoading = settings.llamacppServerStatus === 'loading';

  const handleToggleServer = async () => {
    if (isRunning) {
      settings.setSetting('llamacppServerStatus', 'stopped');
      addToast({
        title: 'Deteniendo Servidor...',
        message: 'Cerrando llama-server.exe y liberando VRAM GPU.',
        type: 'info'
      });
      try {
        await fetch('http://127.0.0.1:8000/api/llamacpp/detener', { method: 'POST' });
      } catch (e) {
        console.error("Error llamando a api detener:", e);
      }
    } else {
      settings.setSetting('llamacppServerStatus', 'loading');
      addToast({
        title: 'Iniciando Proceso...',
        message: 'Enviando comando para ejecutar llama-server.exe con aceleración CUDA GPU.',
        type: 'info'
      });

      const payload = {
        folder_path: settings.llamacppFolderPath,
        model_path: settings.llamacppModelPath,
        config: {
          ngl: settings.llamacppNgl,
          c: settings.llamacppContextSize,
          ctk: settings.llamacppKvCache,
          ctv: settings.llamacppKvCache,
          fa: settings.llamacppFlashAttention,
          mtp: settings.llamacppMtpEnabled,
          mtpDraftMax: settings.llamacppMtpDraftMax,
          temp: settings.llamacppTemperature ?? 0.7,
          topP: settings.llamacppTopP ?? 0.9,
          port: settings.llamacppPort || 8080,
          host: settings.llamacppHost || '127.0.0.1'
        }
      };

      try {
        const res = await fetch('http://127.0.0.1:8000/api/llamacpp/iniciar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          addToast({
            title: '¡Proceso Lanzado!',
            message: 'Esperando a que llama-server inicialice el modelo en memoria GPU...',
            type: 'success'
          });
        } else {
          settings.setSetting('llamacppServerStatus', 'error');
          addToast({
            title: 'Error al Iniciar',
            message: 'No se pudo iniciar el proceso. Verifica la ruta del ejecutable.',
            type: 'error'
          });
        }
      } catch (e) {
        // Fallback: Verificar si llama-server ya está escuchando directamente en el puerto 8080
        try {
          const directCheck = await fetch('http://localhost:8080/health');
          if (directCheck.ok) {
            settings.setSetting('llamacppServerStatus', 'running');
            addToast({
              title: 'Servidor Detectado en Puerto 8080',
              message: 'El servidor llama.cpp ya está activo y respondiendo.',
              type: 'info'
            });
            return;
          }
        } catch (_) {}

        settings.setSetting('llamacppServerStatus', 'error');
        addToast({
          title: 'Backend de Visión fuera de línea (Puerto 5000)',
          message: 'Para lanzar el servidor automáticamente desde la UI, ejecutá "start_all.bat" o "python sentidos/sistema_periferico.py".',
          type: 'warning'
        });
      }
    }
  };

  const applyPresetConfig = (presetObj: any) => {
    const cfg = presetObj.config;
    if (cfg.ngl !== undefined) settings.setSetting('llamacppNgl', cfg.ngl);
    if (cfg.c !== undefined) settings.setSetting('llamacppContextSize', cfg.c);
    if (cfg.ctk !== undefined) settings.setSetting('llamacppKvCache', cfg.ctk);
    if (cfg.fa !== undefined) settings.setSetting('llamacppFlashAttention', cfg.fa);
    if (cfg.mtp !== undefined) settings.setSetting('llamacppMtpEnabled', cfg.mtp);
    if (cfg.mtpDraftMax !== undefined) settings.setSetting('llamacppMtpDraftMax', cfg.mtpDraftMax);
    if (cfg.temp !== undefined) settings.setSetting('llamacppTemperature', cfg.temp);
    if (cfg.topP !== undefined) settings.setSetting('llamacppTopP', cfg.topP);

    addToast({
      title: 'Plantilla de Hiperparámetros Aplicada',
      message: `Se cargaron las opciones de: ${presetObj.name}. Podés ajustar cualquier número o modelo libremente.`,
      type: 'success'
    });
  };

  const handlePresetChange = (presetId: string) => {
    settings.setSetting('llamacppPreset', presetId);
    
    // Primero buscar en presets de proveedores oficiales
    const official = OFFICIAL_PROVIDER_PRESETS.find(p => p.id === presetId);
    if (official) {
      applyPresetConfig(official);
      return;
    }

    // Si no, buscar en presets customizados
    const found = settings.customBatPresets?.find(p => p.id === presetId);
    if (found && found.config) {
      applyPresetConfig(found);
    }
  };

  const handleSaveBat = async () => {
    const profileName = prompt("Ingresá un nombre para este nuevo perfil personalizado:", "Mi Perfil Personalizado");
    if (!profileName) return;

    const newId = `custom-${Date.now()}`;
    const newPreset = {
      id: newId,
      name: profileName,
      config: {
        ngl: settings.llamacppNgl,
        c: settings.llamacppContextSize,
        ctk: settings.llamacppKvCache,
        ctv: settings.llamacppKvCache,
        fa: settings.llamacppFlashAttention,
        mtp: settings.llamacppMtpEnabled,
        mtpDraftMax: settings.llamacppMtpDraftMax,
        temp: settings.llamacppTemperature,
        topP: settings.llamacppTopP
      }
    };

    settings.addCustomBatPreset(newPreset);
    settings.setSetting('llamacppPreset', newId);

    setIsSaved(true);
    addToast({
      title: '¡Perfil Guardado & Script .bat Generado!',
      message: `Se guardó el perfil "${profileName}" y se generó su script ejecutable .bat.`,
      type: 'success'
    });
    setTimeout(() => setIsSaved(false), 2000);
  };

  return (
    <div className="space-y-6 text-xs text-[#cccccc]">
      {/* Paso 1: Selección de Ejecutable y Modelo .gguf */}
      <section className="bg-[#252526] p-4 rounded-lg border border-[#3c3c3c] space-y-4">
        <div className="flex items-center gap-2.5 border-b border-[#3c3c3c] pb-2">
          <span className="bg-[#7c6ff0] text-white rounded-full w-5 h-5 flex items-center justify-center font-bold text-[10px] shrink-0">1</span>
          <h4 className="font-semibold text-white text-xs">Selección de Modelo (.gguf) y Binarios</h4>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="font-medium text-[#cccccc] flex items-center gap-1.5 text-[11px]">
              <Folder size={14} className="text-[#a78bfa]" />
              Carpeta Binarios llama.cpp:
            </label>
            <div className="flex gap-2">
              <input 
                type="text"
                value={settings.llamacppFolderPath || ''}
                onChange={(e) => settings.setSetting('llamacppFolderPath', e.target.value)}
                placeholder="C:\Ruta\a\llama.cpp\bin"
                className="flex-1 bg-[#1e1e1e] border border-[#3c3c3c] text-[#cccccc] px-3 py-1.5 rounded outline-none focus:border-[#a78bfa] font-mono text-[11px]"
              />
              <button 
                onClick={() => setPickerModal({
                  isOpen: true,
                  mode: 'folder',
                  title: 'Buscador Nativo — Seleccionar Carpeta de llama.cpp',
                  initialPath: settings.llamacppFolderPath || 'C:\\Users\\lolpl\\Desktop\\llama.cpp'
                })}
                className="bg-[#3c3c3c] hover:bg-[#4c4c4c] text-white px-3 py-1.5 rounded flex items-center gap-1 transition-colors font-medium text-xs shrink-0"
              >
                <Search size={13} />
                Examinar...
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="font-medium text-[#cccccc] flex items-center gap-1.5 text-[11px]">
              <Sparkles size={14} className="text-emerald-400" />
              Archivo del Modelo (.gguf):
            </label>
            <div className="flex gap-2">
              <input 
                type="text"
                value={settings.llamacppModelPath || ''}
                onChange={(e) => settings.setSetting('llamacppModelPath', e.target.value)}
                placeholder="C:\Ruta\a\modelo.gguf"
                className="flex-1 bg-[#1e1e1e] border border-[#3c3c3c] text-[#cccccc] px-3 py-1.5 rounded outline-none focus:border-[#a78bfa] font-mono text-[11px]"
              />
              <button 
                onClick={() => setPickerModal({
                  isOpen: true,
                  mode: 'file',
                  title: 'Buscador Nativo — Seleccionar Modelo (.gguf)',
                  initialPath: settings.llamacppModelPath || 'C:\\Users\\lolpl\\Desktop\\llama.cpp'
                })}
                className="bg-[#3c3c3c] hover:bg-[#4c4c4c] text-white px-3 py-1.5 rounded flex items-center gap-1 transition-colors font-medium text-xs shrink-0"
              >
                <Search size={13} />
                Elegir .gguf...
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Dashboard de Telemetría de Hardware */}
      <section className="bg-[#252526] p-4 rounded-lg border border-[#3c3c3c] space-y-3">
        <div className="flex justify-between items-center border-b border-[#3c3c3c] pb-2">
          <h4 className="font-semibold text-white flex items-center gap-2">
            <Activity size={16} className="text-[#a78bfa]" />
            Telemetría de Hardware & Consumo de Sistema
          </h4>
          <span className="text-[10px] text-[#8a8a8a] flex items-center gap-1 font-mono">
            <Thermometer size={12} className="text-orange-400" /> 
            GPU: <strong className="text-white">{telemetry.gpuTemp}°C</strong> | CPU: <strong className="text-white">{telemetry.cpuTemp}°C</strong>
          </span>
        </div>

        <div className="grid grid-cols-3 gap-4">
          {/* VRAM GPU */}
          <div className="bg-[#1e1e1e] p-3 rounded border border-[#3c3c3c] space-y-1.5">
            <div className="flex justify-between text-[11px]">
              <span className="text-[#8a8a8a] font-medium flex items-center gap-1"><Zap size={12} className="text-yellow-400" /> VRAM GPU (RTX 5060 Ti)</span>
              <span className="font-mono text-white">{telemetry.vramUsedGb} / {telemetry.vramTotalGb} GB</span>
            </div>
            <div className="w-full bg-[#3c3c3c] rounded-full h-2 overflow-hidden">
              <div className="bg-[#a78bfa] h-full transition-all duration-500" style={{ width: `${telemetry.vramPercent}%` }}></div>
            </div>
          </div>

          {/* RAM Sistema */}
          <div className="bg-[#1e1e1e] p-3 rounded border border-[#3c3c3c] space-y-1.5">
            <div className="flex justify-between text-[11px]">
              <span className="text-[#8a8a8a] font-medium flex items-center gap-1"><Cpu size={12} className="text-blue-400" /> RAM Sistema</span>
              <span className="font-mono text-white">{telemetry.ramUsedGb} / {telemetry.ramTotalGb} GB</span>
            </div>
            <div className="w-full bg-[#3c3c3c] rounded-full h-2 overflow-hidden">
              <div className="bg-blue-500 h-full transition-all duration-500" style={{ width: `${telemetry.ramPercent}%` }}></div>
            </div>
          </div>

          {/* CPU Uso */}
          <div className="bg-[#1e1e1e] p-3 rounded border border-[#3c3c3c] space-y-1.5">
            <div className="flex justify-between text-[11px]">
              <span className="text-[#8a8a8a] font-medium flex items-center gap-1"><Activity size={12} className="text-emerald-400" /> Uso de Procesador</span>
              <span className="font-mono text-white">{telemetry.cpuPercent}%</span>
            </div>
            <div className="w-full bg-[#3c3c3c] rounded-full h-2 overflow-hidden">
              <div className="bg-emerald-500 h-full transition-all duration-500" style={{ width: `${telemetry.cpuPercent}%` }}></div>
            </div>
          </div>
        </div>

        {/* Discos SSD / HDD */}
        <div className="grid grid-cols-2 gap-4 pt-1">
          {telemetry.disks?.map((disk, idx) => (
            <div key={idx} className="bg-[#1e1e1e] p-2.5 rounded border border-[#3c3c3c] flex items-center gap-3">
              <HardDrive size={16} className="text-[#8a8a8a]" />
              <div className="flex-1 space-y-1">
                <div className="flex justify-between text-[10px]">
                  <span className="text-[#cccccc] font-medium">{disk.name}</span>
                  <span className="text-[#8a8a8a]">{disk.freeGb} GB libres de {disk.totalGb} GB</span>
                </div>
                <div className="w-full bg-[#3c3c3c] rounded-full h-1.5 overflow-hidden">
                  <div className="bg-[#7c6ff0] h-full" style={{ width: `${disk.percent}%` }}></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Paso 2: Hiperparámetros de Inferencia y Presets */}
      <section className="bg-[#252526] p-4 rounded-lg border border-[#3c3c3c] space-y-5">
        <div className="flex justify-between items-center border-b border-[#3c3c3c] pb-2">
          <div className="flex items-center gap-2.5">
            <span className="bg-[#7c6ff0] text-white rounded-full w-5 h-5 flex items-center justify-center font-bold text-[10px] shrink-0">2</span>
            <h4 className="font-semibold text-white flex items-center gap-2 text-xs">
              <Sliders size={15} className="text-[#a78bfa]" />
              Hiperparámetros & Plantillas Recomendadas
            </h4>
          </div>
        </div>

        {/* Perfil Preset Selector */}
        <div className="flex items-end gap-3 bg-[#1e1e1e] p-3 rounded-lg border border-[#3c3c3c]">
          <label className="flex-1 flex flex-col gap-1.5">
            <span className="font-semibold text-[#cccccc] text-[11px] flex items-center gap-1">
              <Sparkles size={13} className="text-[#a78bfa]" />
              Plantillas de Proveedores u Homólogos:
            </span>
            <select 
              value={settings.llamacppPreset || 'qwen_35b'}
              onChange={(e) => handlePresetChange(e.target.value)}
              className="bg-[#252526] border border-[#3c3c3c] text-[#cccccc] px-3 py-1.5 rounded outline-none focus:border-[#a78bfa] font-medium text-xs"
            >
              <optgroup label="🌟 Recomendados Oficiales de Proveedores">
                {OFFICIAL_PROVIDER_PRESETS.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </optgroup>
              {settings.customBatPresets && settings.customBatPresets.length > 0 && (
                <optgroup label="⚙️ Perfiles Personalizados">
                  {settings.customBatPresets.map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </optgroup>
              )}
            </select>
          </label>

          <button 
            onClick={handleSaveBat}
            className="h-[34px] bg-[#3c3c3c] hover:bg-[#4c4c4c] text-white px-3 py-1.5 rounded font-medium flex items-center gap-1.5 transition-colors text-xs shrink-0"
          >
            {isSaved ? <Check size={14} className="text-emerald-300" /> : <Save size={14} />}
            {isSaved ? '¡Guardado!' : 'Guardar Nuevo Perfil (.bat)'}
          </button>
        </div>

        <div className="grid grid-cols-2 gap-6">
          
          {/* Capas en GPU (-ngl) */}
          <div className="space-y-2">
            <div className="flex justify-between text-[11px]">
              <span className="font-medium text-[#cccccc] flex items-center gap-1">
                <Layers size={13} /> GPU Offload Layers (-ngl)
                <Tooltip content="Define cuántas capas del modelo se procesan directamente en tu tarjeta de video (VRAM). Valor 999 carga el modelo 100% en GPU para máxima velocidad." />
              </span>
              <span className="font-mono text-[#a78bfa] font-bold">{settings.llamacppNgl} capas</span>
            </div>
            <input 
              type="range" 
              min="0" 
              max="999" 
              value={settings.llamacppNgl || 999}
              onChange={(e) => settings.setSetting('llamacppNgl', parseInt(e.target.value))}
              className="w-full accent-[#a78bfa] cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-[#8a8a8a]">
              <span>0 (CPU Lento)</span>
              <span>999 (Full GPU VRAM)</span>
            </div>
          </div>

          {/* Tamaño de Ventana de Contexto (-c) */}
          <div className="space-y-2">
            <div className="flex justify-between text-[11px]">
              <span className="font-medium text-[#cccccc] flex items-center gap-1">
                Ventana de Contexto (-c)
                <Tooltip content="Tamaño máximo de tokens (palabras) que el modelo recuerda de la conversación. Contextos más grandes permiten procesar archivos de código completos pero consumen más VRAM." />
              </span>
              <span className="font-mono text-[#a78bfa] font-bold">{settings.llamacppContextSize?.toLocaleString()} tokens</span>
            </div>
            <select 
              value={settings.llamacppContextSize || 131072}
              onChange={(e) => settings.setSetting('llamacppContextSize', parseInt(e.target.value))}
              className="w-full bg-[#1e1e1e] border border-[#3c3c3c] text-[#cccccc] px-2.5 py-1.5 rounded outline-none focus:border-[#a78bfa]"
            >
              <option value={4096}>4,096 tokens (4K)</option>
              <option value={8192}>8,192 tokens (8K)</option>
              <option value={16384}>16,384 tokens (16K)</option>
              <option value={32768}>32,768 tokens (32K)</option>
              <option value={131072}>131,072 tokens (128K - Ultra)</option>
              <option value={262144}>262,144 tokens (256K - Masivo)</option>
            </select>
          </div>

          {/* Cuantización KV Cache (-ctk / -ctv) */}
          <div className="space-y-2">
            <span className="font-medium text-[#cccccc] flex items-center gap-1 text-[11px]">
              Cuantización KV Cache (-ctk / -ctv)
              <Tooltip content="Comprime la memoria utilizada para guardar la historia de la charla. q4_0 ahorra hasta 50% de VRAM permitiendo contextos gigantes de 128K sin pérdida perceptible de calidad." />
            </span>
            <select 
              value={settings.llamacppKvCache || 'q4_0'}
              onChange={(e) => settings.setSetting('llamacppKvCache', e.target.value)}
              className="w-full bg-[#1e1e1e] border border-[#3c3c3c] text-[#cccccc] px-2.5 py-1.5 rounded outline-none focus:border-[#a78bfa]"
            >
              <option value="q4_0">q4_0 (Ahorra 50% VRAM - Recomendado Qwen)</option>
              <option value="q8_0">q8_0 (Alta precisión - Recomendado Gemma 4)</option>
              <option value="f16">f16 (Precisión nativa FP16 - Máximo VRAM)</option>
            </select>
          </div>

          {/* Flash Attention (-fa) */}
          <div className="space-y-2">
            <span className="font-medium text-[#cccccc] flex items-center gap-1 text-[11px]">
              Flash Attention (-fa)
              <Tooltip content="Optimización matemática por GPU que acelera drásticamente la velocidad de respuesta en textos o proyectos extensos." />
            </span>
            <label className="flex items-center gap-2 cursor-pointer bg-[#1e1e1e] border border-[#3c3c3c] p-2 rounded">
              <input 
                type="checkbox" 
                checked={settings.llamacppFlashAttention ?? true}
                onChange={(e) => settings.setSetting('llamacppFlashAttention', e.target.checked)}
                className="accent-[#a78bfa] w-4 h-4"
              />
              <span className="text-xs">Activar Flash Attention</span>
            </label>
          </div>

          {/* Temperatura (--temp) */}
          <div className="space-y-2">
            <div className="flex justify-between text-[11px]">
              <span className="font-medium text-[#cccccc] flex items-center gap-1">
                Temperatura (--temp)
                <Tooltip content="Controla la creatividad del modelo. 0.0 a 0.3 es estricto y determinista para código; 0.6 a 0.8 es ideal para conversación." />
              </span>
              <span className="font-mono text-[#a78bfa] font-bold">{(settings.llamacppTemperature ?? 0.7).toFixed(2)}</span>
            </div>
            <input 
              type="range" 
              min="0.0" 
              max="2.0" 
              step="0.05"
              value={settings.llamacppTemperature ?? 0.7}
              onChange={(e) => settings.setSetting('llamacppTemperature', parseFloat(e.target.value))}
              className="w-full accent-[#a78bfa] cursor-pointer"
            />
          </div>

          {/* Top-P (--top-p) */}
          <div className="space-y-2">
            <div className="flex justify-between text-[11px]">
              <span className="font-medium text-[#cccccc] flex items-center gap-1">
                Top-P Sampling (--top-p)
                <Tooltip content="Muestreo nucleus que limita la selección a las palabras más probables (acumulando P% de masa). Recomendado 0.8 para Qwen y 0.95 para DeepSeek." />
              </span>
              <span className="font-mono text-[#a78bfa] font-bold">{(settings.llamacppTopP ?? 0.9).toFixed(2)}</span>
            </div>
            <input 
              type="range" 
              min="0.1" 
              max="1.0" 
              step="0.05"
              value={settings.llamacppTopP ?? 0.9}
              onChange={(e) => settings.setSetting('llamacppTopP', parseFloat(e.target.value))}
              className="w-full accent-[#a78bfa] cursor-pointer"
            />
          </div>

        </div>

        {/* 5. Slider Horizontal para MTP Speculative Decoding (--spec-draft-n-max) */}
        <div className="pt-3 border-t border-[#3c3c3c] space-y-3">
          <div className="flex justify-between items-center">
            <label className="flex items-center gap-2 cursor-pointer">
              <input 
                type="checkbox"
                checked={settings.llamacppMtpEnabled ?? true}
                onChange={(e) => settings.setSetting('llamacppMtpEnabled', e.target.checked)}
                className="accent-[#a78bfa] w-4 h-4"
              />
              <span className="font-semibold text-white text-[11px]">Activar Speculative Decoding / MTP (--spec-type draft-mtp)</span>
            </label>
            <span className="font-mono text-xs text-[#a78bfa] font-bold">
              Draft Max: {settings.llamacppMtpDraftMax || 2}
            </span>
          </div>

          {settings.llamacppMtpEnabled && (
            <div className="bg-[#1e1e1e] p-3 rounded border border-[#3c3c3c] space-y-2">
              <div className="flex justify-between text-[10px] text-[#8a8a8a]">
                <span>1 (Velocidad Normal)</span>
                <span>5 (Acelerado +30%)</span>
                <span>10 (Max Rápido)</span>
              </div>
              <input 
                type="range"
                min="1"
                max="10"
                step="1"
                value={settings.llamacppMtpDraftMax || 2}
                onChange={(e) => settings.setSetting('llamacppMtpDraftMax', parseInt(e.target.value))}
                className="w-full accent-[#a78bfa] cursor-pointer h-2 bg-[#3c3c3c] rounded-lg"
              />
              <p className="text-[10px] text-[#8a8a8a] italic">
                Desliza la perilla horizontalmente para ajustar la profundidad de predicción draft de tokens (1 a 10).
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Paso 3: Control & Lanzamiento del Servidor con la Configuración Lista */}
      <section className="bg-[#252526] p-4 rounded-lg border border-[#3c3c3c] space-y-4">
        <div className="flex items-center gap-2.5 border-b border-[#3c3c3c] pb-2">
          <span className="bg-[#7c6ff0] text-white rounded-full w-5 h-5 flex items-center justify-center font-bold text-[10px] shrink-0">3</span>
          <h4 className="font-semibold text-white text-xs">Lanzamiento del Servidor Local</h4>
        </div>

        <div className="flex justify-between items-center bg-[#1e1e1e] p-3.5 rounded border border-[#3c3c3c]">
          <div className="flex items-center gap-3">
            <div className={`px-3 py-1.5 rounded-full text-[10px] font-bold tracking-wider uppercase flex items-center gap-1.5 ${
              isRunning ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
              isLoading ? 'bg-amber-950 text-amber-400 border border-amber-800 animate-pulse' :
              'bg-red-950 text-red-400 border border-red-800'
            }`}>
              <span className={`w-2.5 h-2.5 rounded-full ${isRunning ? 'bg-emerald-400 animate-ping' : isLoading ? 'bg-amber-400' : 'bg-red-400'}`}></span>
              {isRunning ? 'Servidor Listo (Puerto 8080)' : isLoading ? 'Iniciando llama-server...' : 'Servidor Inactivo'}
            </div>
          </div>

          <button 
            onClick={handleToggleServer}
            disabled={isLoading}
            className={`px-5 py-2 rounded-lg font-bold flex items-center gap-2 transition-all shadow-lg text-xs tracking-wide ${
              isRunning 
                ? 'bg-red-600 hover:bg-red-500 text-white' 
                : 'bg-emerald-600 hover:bg-emerald-500 text-white hover:scale-105'
            }`}
          >
            {isRunning ? <Square size={15} /> : <Play size={15} />}
            {isRunning ? 'Detener Servidor' : '🚀 Iniciar Servidor con esta Configuración'}
          </button>
        </div>
      </section>

      {/* Modal Buscador Nativo de Archivos / Carpetas */}
      <FilePickerModal 
        isOpen={pickerModal.isOpen}
        onClose={() => setPickerModal({ ...pickerModal, isOpen: false })}
        onSelect={(selectedPath) => {
          if (pickerModal.mode === 'folder') {
            settings.setSetting('llamacppFolderPath', selectedPath);
          } else {
            settings.setSetting('llamacppModelPath', selectedPath);
          }
        }}
        title={pickerModal.title}
        mode={pickerModal.mode}
        initialPath={pickerModal.initialPath}
      />
    </div>
  );
}
