import React, { useState, useRef, useEffect } from 'react';
import { useSettingsStore } from '../../stores/useSettingsStore';

type Menu = {
  label: string;
  items: { label: string; action?: () => void; shortcut?: string; divider?: boolean }[];
};

export default function MenuBar() {
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const setSettingsOpen = useSettingsStore((state) => state.setSettingsModalOpen);
  const toggleSidebar = useSettingsStore((state) => state.toggleSidebar);
  const setActiveSidebarTab = useSettingsStore((state) => state.setActiveSidebarTab);

  const menus: Menu[] = [
    {
      label: 'Archivo',
      items: [
        { 
          label: 'Abrir Carpeta...', 
          shortcut: 'Ctrl+K Ctrl+O',
          action: () => {
            setActiveSidebarTab('explorer');
          }
        },
        { divider: true },
        { label: 'Preferencias', action: () => setSettingsOpen(true), shortcut: 'Ctrl+,' }
      ]
    },
    {
      label: 'Editar',
      items: [
        { label: 'Deshacer', shortcut: 'Ctrl+Z' },
        { label: 'Rehacer', shortcut: 'Ctrl+Y' }
      ]
    },
    {
      label: 'Ver',
      items: [
        { 
          label: 'Alternar Barra Lateral', 
          shortcut: 'Ctrl+B', 
          action: () => toggleSidebar() 
        },
        { divider: true },
        { 
          label: 'Alternar Terminal', 
          shortcut: 'Ctrl+`', 
          action: () => {
            const store = useSettingsStore.getState();
            store.setTerminalOpen(!store.isTerminalOpen);
          } 
        }
      ]
    },
    {
      label: 'Terminal',
      items: [
        { 
          label: 'Nueva Terminal', 
          shortcut: 'Ctrl+Shift+`',
          action: () => {
            useSettingsStore.getState().setTerminalOpen(true);
          }
        }
      ]
    },
    {
      label: 'Ayuda',
      items: [
        { label: 'Acerca de Visión Studio 2.0' }
      ]
    }
  ];

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setActiveMenu(null);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="menubar relative select-none" ref={menuRef}>
      {menus.map((menu) => (
        <div key={menu.label} className="relative inline-block">
          <span 
            className={`px-2 py-1 cursor-default hover:bg-[#3c3c3c] rounded ${activeMenu === menu.label ? 'bg-[#3c3c3c]' : ''}`}
            onClick={() => setActiveMenu(activeMenu === menu.label ? null : menu.label)}
          >
            {menu.label}
          </span>
          
          {activeMenu === menu.label && (
            <div className="absolute top-full left-0 mt-1 w-64 bg-[#252526] border border-[#3c3c3c] shadow-lg rounded-md py-1 z-50 flex flex-col text-[13px]">
              {menu.items.map((item, idx) => (
                item.divider ? (
                  <div key={idx} className="h-px bg-[#3c3c3c] my-1 mx-2" />
                ) : (
                  <div 
                    key={idx} 
                    className="flex justify-between items-center px-6 py-1.5 hover:bg-[#04395e] cursor-pointer text-[#cccccc] hover:text-white"
                    onClick={() => {
                      item.action?.();
                      setActiveMenu(null);
                    }}
                  >
                    <span>{item.label}</span>
                    {item.shortcut && <span className="text-[#8a8a8a] text-xs">{item.shortcut}</span>}
                  </div>
                )
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
