import React from 'react';
import { useSettingsStore } from '../../stores/useSettingsStore';

export default function TitleBar() {
  const llmMode = useSettingsStore(state => state.llmMode);
  const setLlmMode = useSettingsStore(state => state.setLlmMode);

  return (
    <div className="titlebar" data-tauri-drag-region>
      <div className="traffic-lights">
        <span 
          className="tl-red" 
          onClick={() => setLlmMode('free')}
          title="Modo Free"
          style={{ boxShadow: llmMode === 'free' ? '0 0 8px #ff5f56' : 'none', opacity: llmMode === 'free' ? 1 : 0.5 }}
        ></span>
        <span 
          className="tl-yellow" 
          onClick={() => setLlmMode('hybrid')}
          title="Modo Híbrido"
          style={{ boxShadow: llmMode === 'hybrid' ? '0 0 8px #ffbd2e' : 'none', opacity: llmMode === 'hybrid' ? 1 : 0.5 }}
        ></span>
        <span 
          className="tl-green" 
          onClick={() => setLlmMode('paid')}
          title="Modo Paid"
          style={{ boxShadow: llmMode === 'paid' ? '0 0 8px #27c93f' : 'none', opacity: llmMode === 'paid' ? 1 : 0.5 }}
        ></span>
      </div>
      <div className="titlebar-title" data-tauri-drag-region>
        <svg width="13" height="13" viewBox="0 0 24 24">
          <defs>
            <linearGradient id="gLogo" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#7c6ff0"/>
              <stop offset="100%" stopColor="#c084fc"/>
            </linearGradient>
          </defs>
          <path fill="url(#gLogo)" d="M12 2l1.8 5.6L19 9.5l-5.2 1.9L12 17l-1.8-5.6L5 9.5l5.2-1.9L12 2z"/>
        </svg>
        vision-studio — cognitive-agent <span className="opacity-50 ml-2 text-[10px] uppercase">[{llmMode}]</span>
      </div>
      <div className="titlebar-spacer"></div>
    </div>
  );
}
