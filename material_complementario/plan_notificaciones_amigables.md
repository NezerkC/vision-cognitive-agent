# Plan de Implementación: Sistema de Notificaciones, Banners y Guiado Amigable (UX/UI)

Este plan detalla el diseño e implementación de un sistema unificado de **Notificaciones Toast**, **Carteles Informativos (Banners)**, **Tooltips Explicativos** e **Indicadores de Estado** dentro de Vision Studio. El objetivo es eliminar cualquier ambigüedad técnica y guiar al usuario amigablemente sobre el estado de la inferencia, servidores, memoria VRAM y errores.

---

## User Review Required

> [!IMPORTANT]
> - **Ubicación de Notificaciones (Toasts)**: Las notificaciones emergentes se mostrarán flotando en la esquina inferior derecha de la pantalla con auto-cierre a los 4 segundos.
> - **Explicaciones en Lenguaje Claro**: Todos los términos técnicos (`-ngl`, `MTP`, `KV Cache`, `VAD`) tendrán íconos de ayuda `(?)` con descripciones simples sin jerga complicada.

---

## Open Questions

> [!NOTE]
> 1. ¿Sonidos de Notificación?: ¿Te gustaría agregar efectos de sonido sutiles y amigables al conectarse el servidor o al ocurrir un error?

---

## Proposed Changes

### Vision Studio Frontend UI

#### [NEW] [useNotificationStore.ts](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/stores/useNotificationStore.ts)
- Store de Zustand dedicado para manejar la cola de notificaciones flotantes:
  - `toasts`: Lista de notificaciones (`id`, `title`, `message`, `type: 'success' | 'error' | 'warning' | 'info'`, `duration`).
  - `addToast(toast)`: Función para emitir un mensaje.
  - `removeToast(id)`: Función para eliminar un mensaje.

#### [NEW] [ToastContainer.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Notifications/ToastContainer.tsx)
- Componente flotante posicionado en la esquina inferior derecha:
  - Notificaciones estilo tarjeta oscura con bordes coloreados y animación slide-in:
    - 🟢 **Éxito**: *"Servidor Llama.cpp iniciado correctamente en puerto 8080"*.
    - 🔴 **Error**: *"No se pudo conectar con el servidor local. Verificá si el puerto está libre"*.
    - 🟡 **Advertencia**: *"VRAM alta (85%). Considerá reducir la ventana de contexto a 32K"*.
    - 🔵 **Información**: *"Modelo liberado de VRAM para iniciar Qwen 35B"*.

#### [NEW] [Tooltip.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/UI/Tooltip.tsx)
- Componente reutilizable de tooltip informativo:
  - Muestra un globito explicativo flotante al pasar el cursor sobre cualquier ícono `(?)` o etiqueta técnica.

#### [MODIFY] [LlamaCppPanel.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Settings/LlamaCppPanel.tsx)
- Agregar carteles explicativos amigables (`BannerHelp`) al inicio de cada sección:
  - Banner en **Ruta de Binarios**: *"💡 Tip: Seleccioná la carpeta donde tenés llama-server.exe para que Vision maneje la carga automáticamente."*
  - Banner en **Hiperparámetros**: *"🚀 MTP acelera la generación un 30% usando un modelo borrador en paralelo."*
  - Integrar tooltips `(?)` en todos los parámetros técnicos.
  - Disparar `addToast()` cuando el servidor inicie, se detenga o se guarde un `.bat`.

#### [MODIFY] [SidebarChat.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Sidebar/SidebarChat.tsx)
- Emitir notificaciones amigables si una llamada falla o si el proveedor cambia.

---

### Python Backend / Event Broadcaster

#### [MODIFY] [gestor_llamacpp.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/gestor_llamacpp.py)
- Retornar estados estructurados y mensajes de error humanos para que el frontend emita notificaciones claras si un proceso falla.

---

## Verification Plan

### Automated Tests
- Probar la emisión de tostadas ejecutando pruebas unitarias o llamadas simuladas en el store de notificaciones.

### Manual Verification
1. Abrir **Vision Studio** e interactuar con el panel de Llama.cpp.
2. Hacer clic en **Iniciar Servidor** y comprobar la aparición de la notificación flotante verde en la esquina.
3. Simular una desconexión o ruta inválida y verificar que la notificación roja explique claramente qué ocurrió.
4. Pasar el mouse sobre los íconos `(?)` en el panel y verificar que los tooltips se lean con lenguaje amigable.
