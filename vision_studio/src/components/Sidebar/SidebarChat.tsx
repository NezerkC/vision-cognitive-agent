import React, { useState } from 'react';
import { Send, Bot, User, MessageSquare, ClipboardList, Hammer, Search, Zap, Clock, Terminal, FileCode, FileText } from 'lucide-react';
import EmotionState from './EmotionState';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { invoke } from '@tauri-apps/api/core';
import ToolApprovalModal, { ToolApprovalRequest } from '../UI/ToolApprovalModal';

const executeWebSearch = async (query: string) => {
  try {
    const result = await invoke<string>('web_search_duckduckgo', { query });
    return result;
  } catch (err) {
    return `Error al realizar la búsqueda web: ${err}`;
  }
};

const TOOLS = [
  {
    type: "function",
    function: {
      name: "web_search",
      description: "Busca información en internet de forma anónima usando DuckDuckGo. Usa esto cuando necesites datos reales, noticias recientes o sobre personas, lugares o conceptos técnicos que no conoces. Recibirás fragmentos de texto de los mejores resultados.",
      parameters: {
        type: "object",
        properties: {
          query: {
            type: "string",
            description: "El término o pregunta a buscar."
          }
        },
        required: ["query"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "read_file",
      description: "Lee el contenido de un archivo existente en el sistema de archivos.",
      parameters: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description: "La ruta completa o relativa del archivo a leer."
          }
        },
        required: ["path"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "write_file",
      description: "Crea o sobreescribe un archivo en disco con el contenido textual especificado.",
      parameters: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description: "La ruta absoluta o relativa del archivo a crear/editar."
          },
          content: {
            type: "string",
            description: "El contenido textual completo a escribir."
          }
        },
        required: ["path", "content"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "execute_powershell",
      description: "Ejecuta un comando en PowerShell de Windows (npm, git, ruff, pytest, etc.) y retorna stdout, stderr y exit_code.",
      parameters: {
        type: "object",
        properties: {
          command: {
            type: "string",
            description: "El comando de PowerShell a ejecutar."
          },
          cwd: {
            type: "string",
            description: "Opcional. El directorio de trabajo donde ejecutar el comando."
          }
        },
        required: ["command"]
      }
    }
  }
];

type ChatMode = 'normal' | 'plan' | 'build';

export default function SidebarChat() {
  const settings = useSettingsStore();
  const [messages, setMessages] = useState<any[]>([
    { role: 'assistant', text: '¡Hola! Soy tu agente cognitivo. ¿En qué puedo ayudarte hoy?' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [chatMode, setChatMode] = useState<ChatMode>('normal');
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [approvalRequest, setApprovalRequest] = useState<ToolApprovalRequest | null>(null);

  const requestToolApproval = (toolName: string, args: any): Promise<boolean> => {
    return new Promise((resolve) => {
      setApprovalRequest({
        toolName,
        args,
        onApprove: () => {
          setApprovalRequest(null);
          resolve(true);
        },
        onReject: () => {
          setApprovalRequest(null);
          resolve(false);
        }
      });
    });
  };

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;
    
    const userMessage = { role: 'user', text: input };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsTyping(true);
    setActionStatus(null);

    let currentContext = [...newMessages];
    let systemPrompt = "";
    let currentTemperature = 0.7;

    if (chatMode === 'plan') {
      systemPrompt = `Eres un Arquitecto de Software Experto.
Tu objetivo es analizar la petición del usuario y crear un PLAN de implementación detallado paso a paso.
REGLAS:
1. Responde ÚNICAMENTE con el plan estructurado en Markdown.
2. Incluye: Resumen del objetivo, Análisis de requerimientos, Arquitectura/Diseño, y Lista de tareas secuenciales.
3. Antes de planear, investiga usando la herramienta web_search o read_file si necesitas inspeccionar archivos.`;
      currentTemperature = 0.3;
    } else if (chatMode === 'build') {
      systemPrompt = `Eres un Ingeniero de Software Senior y Agente Autónomo en Visión OS.
Tu objetivo es ejecutar planes de desarrollo, explorar archivos del workspace, escribir/editar código y ejecutar comandos de prueba o construcción.
REGLAS Y HERRAMIENTAS DISPONIBLES:
1. Podés usar las siguientes herramientas nativas:
   - read_file(path): Inspecciona archivos existentes antes de editar.
   - write_file(path, content): Crea nuevos archivos o guarda cambios de código.
   - execute_powershell(command, cwd): Ejecuta pruebas (pytest, npm test), linters (ruff) o tareas en la terminal.
   - web_search(query): Busca documentación técnica o librerías en internet.
2. SIEMPRE lee el contenido de un archivo con read_file antes de escribir modificaciones si el archivo ya existe.
3. Explica brevemente tu plan antes de invocar herramientas. Usa bloques de código Markdown con el lenguaje correspondiente.`;
      currentTemperature = 0.1;
    }
    
    let apiMessages = currentContext.map(m => {
      if (m.role === 'tool') {
        return { role: 'tool', tool_call_id: m.tool_call_id, name: m.name, content: m.text };
      }
      if (m.tool_calls) {
        return { role: 'assistant', tool_calls: m.tool_calls, content: m.text || "" };
      }
      return { role: m.role, content: m.text };
    });

    if (systemPrompt) {
      apiMessages = [{ role: 'system', content: systemPrompt }, ...apiMessages];
    }

    try {
      const activeModel = settings.providerModels?.[settings.provider] || settings.model;
      let isAgentLooping = true;
      let loopCount = 0;

      while (isAgentLooping && loopCount < 8) {
        loopCount++;
        let responseData: any = null;
        const startTime = Date.now();

        if (settings.provider === 'openrouter' || settings.provider === 'llamacpp' || settings.provider === 'lmstudio') {
          const defaultEndpoint = settings.provider === 'openrouter' 
            ? "https://openrouter.ai/api/v1" 
            : (settings.provider === 'llamacpp' ? "http://localhost:8080/v1" : "http://localhost:1234/v1");
          
          let baseEndpoint = settings.provider === 'openrouter' ? defaultEndpoint : (settings.endpoints?.[settings.provider] || defaultEndpoint);
          if (baseEndpoint.endsWith('/')) {
            baseEndpoint = baseEndpoint.slice(0, -1);
          }
          const endpoint = `${baseEndpoint}/chat/completions`;
            
          const headers: any = { "Content-Type": "application/json" };
          if (settings.provider === 'openrouter') {
            const apiKey = settings.apiKeys['openrouter'];
            if (!apiKey) throw new Error("API Key de OpenRouter no configurada.");
            headers["Authorization"] = `Bearer ${apiKey}`;
          }

          const response = await fetch(endpoint, {
            method: "POST",
            headers,
            body: JSON.stringify({
              model: activeModel || (settings.provider === 'openrouter' ? "google/gemini-1.5-pro" : "local-model"),
              messages: apiMessages,
              tools: TOOLS,
              tool_choice: "auto",
              temperature: currentTemperature
            })
          });
          
          responseData = await response.json();
          if (responseData.error) throw new Error(responseData.error.message || JSON.stringify(responseData.error));
        } 
        else if (settings.provider === 'ollama') {
          let baseUrl = settings.endpoints?.['ollama'] || "http://localhost:11434";
          if (baseUrl.endsWith('/')) baseUrl = baseUrl.slice(0, -1);

          const response = await fetch(`${baseUrl}/api/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              model: activeModel || "llama3",
              messages: apiMessages,
              tools: TOOLS,
              stream: false,
              options: {
                temperature: currentTemperature
              }
            })
          });
          
          responseData = await response.json();
          if (responseData.error) throw new Error(responseData.error);
          
          if (responseData.message) {
            responseData.choices = [{ message: responseData.message }];
          }
        } 
        else {
          throw new Error(`Conexión con '${settings.provider}' no implementada.`);
        }

        const durationSec = (Date.now() - startTime) / 1000;
        const choice = responseData.choices[0].message;

        let content = choice.content || "";
        let reasoning = choice.reasoning || choice.reasoning_content || "";
        
        const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/);
        if (thinkMatch) {
          reasoning = reasoning ? reasoning + "\n\n" + thinkMatch[1].trim() : thinkMatch[1].trim();
          content = content.replace(/<think>[\s\S]*?<\/think>/, '').trim();
        }

        const estTokens = Math.max(1, Math.round((content.length + (reasoning ? reasoning.length : 0)) / 4));
        const tokensPerSec = durationSec > 0 ? (estTokens / durationSec).toFixed(1) : "N/A";
        const contextUsed = Math.min(100, Math.round((apiMessages.reduce((acc, m) => acc + (m.content?.length || 0), 0) / 4 / (settings.llamacppContextSize || 131072)) * 100));

        const metrics = {
          tokens: estTokens,
          tokensPerSec,
          durationSec: durationSec.toFixed(2),
          contextUsed
        };

        if (choice.tool_calls && choice.tool_calls.length > 0) {
          const toolCall = choice.tool_calls[0]; 
          const toolName = toolCall.function.name;
          
          const assistantMessage = { role: 'assistant', text: content, reasoning, metrics, tool_calls: choice.tool_calls };
          setMessages(prev => [...prev, assistantMessage]);
          apiMessages.push({ role: 'assistant', content: choice.content || "", tool_calls: choice.tool_calls });

          let args: any = {};
          try {
            args = JSON.parse(toolCall.function.arguments);
          } catch (e) {
            args = { raw: toolCall.function.arguments };
          }

          let toolResult = "";

          if (toolName === 'web_search') {
            setActionStatus(`Buscando en DuckDuckGo: "${args.query}"...`);
            toolResult = await executeWebSearch(args.query);
          } else if (toolName === 'read_file') {
            setActionStatus(`Leyendo archivo: ${args.path}...`);
            try {
              toolResult = await invoke<string>('read_file_content', { path: args.path });
            } catch (err) {
              toolResult = `Error al leer archivo: ${err}`;
            }
          } else if (toolName === 'write_file' || toolName === 'execute_powershell') {
            const permLevel = settings.permissionLevel || 'ask';

            if (permLevel === 'read_only') {
              toolResult = `Error: La ejecución de ${toolName} está bloqueada porque el agente está configurado en nivel 'Solo Lectura'.`;
            } else {
              let isApproved = true;
              if (permLevel === 'ask') {
                setActionStatus(`Solicitando permiso para ejecutar ${toolName}...`);
                isApproved = await requestToolApproval(toolName, args);
              }

              if (!isApproved) {
                toolResult = `Operación cancelada: El usuario rechazó la ejecución de ${toolName}.`;
              } else {
                if (toolName === 'write_file') {
                  setActionStatus(`Escribiendo archivo: ${args.path}...`);
                  try {
                    toolResult = await invoke<string>('write_file_content', { path: args.path, content: args.content });
                  } catch (err) {
                    toolResult = `Error al escribir archivo: ${err}`;
                  }
                } else if (toolName === 'execute_powershell') {
                  setActionStatus(`Ejecutando PowerShell: ${args.command}...`);
                  try {
                    const execRes = await invoke<any>('execute_powershell_command', { 
                      command: args.command, 
                      cwd: args.cwd || settings.currentWorkspacePath 
                    });
                    toolResult = `Exit Code: ${execRes.exit_code}\nSTDOUT:\n${execRes.stdout}\nSTDERR:\n${execRes.stderr}`;
                  } catch (err) {
                    toolResult = `Error al ejecutar comando PowerShell: ${err}`;
                  }
                }
              }
            }
          } else {
            toolResult = "Error: Herramienta no implementada.";
          }

          const toolMessage = { role: 'tool', tool_call_id: toolCall.id, name: toolName, text: toolResult };
          setMessages(prev => [...prev, toolMessage]);
          apiMessages.push({ role: 'tool', tool_call_id: toolCall.id, name: toolName, content: toolResult });
          setActionStatus(null);
        } else {
          setMessages(prev => [...prev, { role: 'assistant', text: content, reasoning, metrics }]);
          apiMessages.push({ role: 'assistant', content: choice.content || "" });
          isAgentLooping = false;
        }
      }
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'assistant', text: `Error: ${err.message}` }]);
    } finally {
      setIsTyping(false);
      setActionStatus(null);
    }
  };

  return (
    <div className="flex flex-col h-full w-full max-w-full overflow-hidden relative bg-[#181819] text-xs">
      <EmotionState />
      <ToolApprovalModal request={approvalRequest} />
      
      {/* Mode Selector */}
      <div className="flex bg-[#202021] p-1.5 border-b border-[#3c3c3c] gap-1">
        <button 
          onClick={() => setChatMode('normal')}
          className={`flex-1 py-1.5 flex items-center justify-center gap-1.5 text-[10px] uppercase font-semibold rounded-md transition-all ${
            chatMode === 'normal' ? 'bg-[#37373d] text-white shadow-sm' : 'text-[#8a8a8a] hover:text-[#cccccc] hover:bg-[#2a2a2c]'
          }`}
        >
          <MessageSquare size={12} className={chatMode === 'normal' ? 'text-[#a78bfa]' : ''} /> Normal
        </button>
        <button 
          onClick={() => setChatMode('plan')}
          className={`flex-1 py-1.5 flex items-center justify-center gap-1.5 text-[10px] uppercase font-semibold rounded-md transition-all ${
            chatMode === 'plan' ? 'bg-[#007acc] text-white shadow-sm' : 'text-[#8a8a8a] hover:text-[#cccccc] hover:bg-[#2a2a2c]'
          }`}
        >
          <ClipboardList size={12} /> Plan
        </button>
        <button 
          onClick={() => setChatMode('build')}
          className={`flex-1 py-1.5 flex items-center justify-center gap-1.5 text-[10px] uppercase font-semibold rounded-md transition-all ${
            chatMode === 'build' ? 'bg-[#7c6ff0] text-white shadow-sm' : 'text-[#8a8a8a] hover:text-[#cccccc] hover:bg-[#2a2a2c]'
          }`}
        >
          <Hammer size={12} /> Build
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-3 space-y-3 custom-scrollbar w-full">
        {messages.map((msg, i) => {
          if (msg.role === 'tool') {
            const isPS = msg.name === 'execute_powershell';
            const isFile = msg.name === 'read_file' || msg.name === 'write_file';
            
            return (
              <div key={i} className="flex gap-2 text-[#8a8a8a] text-[10px] font-mono w-full bg-[#202021] p-2.5 border border-[#3c3c3c] rounded-xl items-start break-words overflow-hidden">
                {isPS ? (
                  <Terminal size={14} className="text-emerald-400 shrink-0 mt-0.5" />
                ) : isFile ? (
                  <FileCode size={14} className="text-[#a78bfa] shrink-0 mt-0.5" />
                ) : (
                  <Search size={14} className="text-blue-400 shrink-0 mt-0.5" />
                )}
                <div className="flex-1 min-w-0 break-words space-y-1">
                  <div className="flex items-center gap-1.5 text-white font-bold">
                    <span>Resultado de <code className="text-[#a78bfa] font-mono">{msg.name}</code>:</span>
                  </div>
                  <pre className="text-[#cccccc] text-[10.5px] whitespace-pre-wrap font-mono custom-scrollbar max-h-40 overflow-y-auto bg-[#141415] p-2 rounded border border-[#3c3c3e]">
                    {msg.text}
                  </pre>
                </div>
              </div>
            );
          }

          const hasToolCalls = msg.tool_calls && msg.tool_calls.length > 0;
          const isUser = msg.role === 'user';

          return (
            <div key={i} className={`flex gap-2.5 w-full min-w-0 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 shadow-sm mt-0.5 ${
                isUser ? 'bg-[#7c6ff0] text-white' : 'bg-[#2b2b2c] border border-[#3c3c3c] text-[#a78bfa]'
              }`}>
                {isUser ? <User size={13} /> : <Bot size={13} />}
              </div>
              
              <div className={`flex flex-col min-w-0 max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
                {(msg.text || msg.reasoning || hasToolCalls) && (
                  <div className={`px-3.5 py-2.5 rounded-2xl shadow-sm text-xs leading-relaxed break-words overflow-hidden w-full ${
                    isUser 
                      ? 'bg-gradient-to-r from-[#7c6ff0] to-[#6366f1] text-white rounded-tr-xs' 
                      : 'bg-[#252526] border border-[#3c3c3c] text-[#e0e0e0] rounded-tl-xs'
                  }`}>
                    {msg.reasoning && (
                      <details className="mb-2 bg-[#1b1b1c] border border-[#3c3c3c] rounded-lg p-2 overflow-hidden">
                        <summary className="text-[#a78bfa] text-[10px] font-bold outline-none cursor-pointer select-none flex items-center gap-1">
                          🧠 Razonamiento Largo
                        </summary>
                        <div className="mt-2 text-[#9a9a9a] text-[10px] whitespace-pre-wrap font-mono custom-scrollbar max-h-48 overflow-y-auto overflow-x-hidden break-words">
                          {msg.reasoning}
                        </div>
                      </details>
                    )}

                    {msg.text && (
                      <div className="whitespace-pre-wrap break-words overflow-hidden w-full leading-normal">
                        {msg.text}
                      </div>
                    )}

                    {hasToolCalls && (
                      <div className="text-[#a78bfa] italic mt-1.5 font-mono text-[10px] flex items-center gap-1 bg-[#1b1b1c] p-1.5 rounded border border-[#3c3c3e]">
                        <Terminal size={11} className="animate-pulse" /> Ejecutando herramienta del sistema...
                      </div>
                    )}

                    {!isUser && msg.metrics && (
                      <div className="mt-2 pt-1.5 border-t border-[#3c3c3c] flex items-center justify-between text-[9.5px] text-[#a78bfa] font-mono gap-2 flex-wrap">
                        <span className="flex items-center gap-1">
                          <Zap size={10} className="text-amber-400" />
                          <strong>{msg.metrics.tokensPerSec} t/s</strong> ({msg.metrics.tokens} tokens)
                        </span>
                        <span className="text-[#8a8a8a] flex items-center gap-1">
                          <Clock size={9} /> {msg.metrics.durationSec}s | Ctx: {msg.metrics.contextUsed}%
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {actionStatus && (
          <div className="text-[10px] text-[#a78bfa] italic flex items-center gap-2 animate-pulse bg-[#202021] p-2 rounded-lg border border-[#3c3c3c] w-full">
            <Terminal size={11} /> {actionStatus}
          </div>
        )}
      </div>
      
      {/* Input Area */}
      <div className="p-3 border-t border-[#3c3c3c] bg-[#1e1e1f]">
        <div className="relative flex items-center">
          <textarea 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={
              chatMode === 'normal' 
                ? "Escribí tu consulta..." 
                : chatMode === 'plan' 
                ? "Definí el problema a planear..." 
                : "Instrucciones de construcción y código..."
            } 
            className="w-full bg-[#252526] border border-[#3c3c3c] focus:border-[#7c6ff0] rounded-xl text-[#e0e0e0] text-xs p-3 pr-10 outline-none resize-none h-[72px] custom-scrollbar leading-relaxed"
          />
          <button 
            onClick={handleSend}
            disabled={isTyping || !input.trim()}
            className="absolute right-2.5 bottom-2.5 bg-[#7c6ff0] hover:bg-[#6366f1] disabled:opacity-30 disabled:hover:bg-[#7c6ff0] text-white p-1.5 rounded-lg transition-all shadow-md flex items-center justify-center"
          >
            <Send size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}
