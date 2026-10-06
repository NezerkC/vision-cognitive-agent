import { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

export default function IntegratedTerminal() {
  const terminalRef = useRef<HTMLDivElement>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);

  useEffect(() => {
    if (!terminalRef.current) return;

    // Inicializar terminal
    const term = new Terminal({
      theme: {
        background: '#1e1e1e',
        foreground: '#cccccc',
        cursor: '#ffffff'
      },
      fontFamily: 'monospace',
      fontSize: 13,
      cursorBlink: true
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    fitAddonRef.current = fitAddon;

    term.open(terminalRef.current);
    fitAddon.fit();

    term.writeln('\x1b[1;32mVisión OS 2.0\x1b[0m - Sandbox Terminal');
    term.write('\r\n$ ');

    // Ajustar el tamaño cuando la ventana cambia
    const handleResize = () => {
      fitAddon.fit();
    };
    window.addEventListener('resize', handleResize);

    // Pequeño timeout para asegurar que el contenedor está renderizado antes del fit
    const fitTimer = setTimeout(() => fitAddon.fit(), 100);

    return () => {
      // Cancel the pending fit: running it on a disposed terminal throws inside xterm's viewport.
      clearTimeout(fitTimer);
      window.removeEventListener('resize', handleResize);
      term.dispose();
    };
  }, []);

  return (
    <div className="terminal-output" ref={terminalRef}></div>
  );
}
