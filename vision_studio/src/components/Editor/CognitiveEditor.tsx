import React, { useState } from 'react';
import Editor from '@monaco-editor/react';
import ChatOverlay from './ChatOverlay';

export default function CognitiveEditor() {
  const [code, setCode] = useState<string>('# Bienvenido a Visión Studio\n\ndef main():\n    print("Iniciando análisis cognitivo...")\n\nif __name__ == "__main__":\n    main()\n');

  function handleEditorChange(value: string | undefined) {
    if (value !== undefined) {
      setCode(value);
    }
  }

  return (
    <div className="w-full h-full flex flex-col bg-[#1e1e1e] overflow-hidden relative">
      <div className="tabs flex justify-between" id="tabsBar">
        <div className="flex">
          <div className="tab active">
            <span className="file-badge badge-js">JS</span>
            <span className="tab-name">main.py</span>
            <span className="tab-close">✕</span>
          </div>
        </div>
        <div className="flex items-center gap-3 pr-4 text-[#8a8a8a]">
          <button className="hover:text-[#cccccc] transition-colors flex items-center justify-center" title="Ejecutar Archivo (Run)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          </button>
          <button className="hover:text-[#cccccc] transition-colors flex items-center justify-center" title="Dividir Editor a la Derecha">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="12" y1="3" x2="12" y2="21"></line></svg>
          </button>
          <button className="hover:text-[#cccccc] transition-colors flex items-center justify-center" title="Más Acciones">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle><circle cx="5" cy="12" r="1"></circle></svg>
          </button>
        </div>
      </div>
      <div className="breadcrumb" id="breadcrumb">
        workspace <span className="crumb-sep">›</span> main.py
      </div>

      <div className="flex-grow relative">
        <Editor
          height="100%"
          defaultLanguage="python"
          theme="vs-dark"
          value={code}
          onChange={handleEditorChange}
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            wordWrap: 'on',
            lineNumbersMinChars: 3,
            padding: { top: 16 },
            scrollBeyondLastLine: false,
            smoothScrolling: true,
          }}
        />
        <ChatOverlay />
      </div>
    </div>
  );
}
