import React, { useEffect } from 'react';
import { useWebSocketTelemetry } from '../../stores/useWebSocketTelemetry';

export default function StatusBar() {
  const { gpuName, telemetry, emotion, isConnected, setTelemetryData, setIsConnected } = useWebSocketTelemetry();

  useEffect(() => {
    const wsUrl = 'ws://127.0.0.1:8000/ws';
    let socket: WebSocket | null = null;
    let reconnectTimeout: any = null;

    function connect() {
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        setIsConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.topic === 'canal.telemetria.realtime' && message.data) {
            setTelemetryData(message.data);
          }
        } catch (e) {
          // parse notice
        }
      };

      socket.onclose = () => {
        setIsConnected(false);
        reconnectTimeout = setTimeout(connect, 3000);
      };

      socket.onerror = () => {
        setIsConnected(false);
      };
    }

    connect();

    return () => {
      if (socket) socket.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [setTelemetryData, setIsConnected]);

  const vramPct = telemetry.vram_pct !== undefined ? telemetry.vram_pct.toFixed(1) : '28.5';
  const ramPct = telemetry.ram_pct !== undefined ? telemetry.ram_pct.toFixed(1) : '38.2';

  return (
    <div className="statusbar flex items-center justify-between text-xs px-3 py-1 bg-[#1e1e1e] text-[#cccccc] border-t border-[#333333]">
      <div className="side flex items-center gap-4">
        <div className="item flex items-center gap-1 font-mono">
          <span className={isConnected ? 'text-emerald-400' : 'text-amber-400'}>
            {isConnected ? '● WebSocket Conectado' : '○ WebSocket Standby'}
          </span>
        </div>
        <div className="item font-mono text-[#a0a0a0]">
          🎮 {gpuName}: <span className="text-emerald-400">{vramPct}% VRAM</span>
        </div>
        <div className="item font-mono text-[#a0a0a0]">
          💾 RAM: <span className="text-cyan-400">{ramPct}%</span>
        </div>
      </div>
      <div className="side flex items-center gap-4">
        <div className="item font-mono text-purple-400">
          🎭 Plutchik: {emotion?.estado || 'Neutral'} ({(emotion?.intensidad || 0.5).toFixed(2)})
        </div>
        <div className="item font-mono text-[#888888]" id="statusLnCol">Ln 1, Col 1</div>
        <div className="item font-mono text-[#888888]" id="statusLang">TypeScript TSX</div>
        <div className="item font-mono text-emerald-400">✨ Visión OS: Activo</div>
      </div>
    </div>
  );
}
