# Registro de Cambios: Implementación Backend v2 (Zapatilla Eléctrica & Puerto Multimodal)

## Fecha
Julio 2026

## Componentes Implementados

### 1. Orquestación y Memoria 4D
- Se migró la base de datos `memoria_activa` (LanceDB) a un esquema **4D** (Coordenadas X, Y, Z, W).
- Se implementó la lógica en `lancedb_manager.py` para usar Full-Text Search (FTS) e índices vectoriales para **Progressive RAG**.
- Se corrigió la integración en `orquestador_graph.py` y `llm_router.py` para que el agente filtre los recuerdos según su estado emocional antes de realizar la búsqueda densa.

### 2. Zapatilla Eléctrica (Protocolo Intriga)
- Se habilitó la lógica de auto-capacitación en `protocolo_intriga.py`.
- Cuando se detecta un nuevo CLI (mapeado desde el Host por el `contexto_derecho.py`), el orquestador ahora lanza una búsqueda, genera el código del tool (Python) y lo guarda en la memoria usando las coordenadas 4D.

### 3. Puerto de Ingestión Multimodal
- En `sentidos/sistema_periferico.py` se agregó la ruta FastAPI `POST /api/memoria/aprender`.
- Soporta subida de archivos (MIME Types) para:
  - **PDF (`application/pdf`)**: Procesado con `PyPDFLoader` y enviado al canal de memoria.
  - **CSV (`text/csv`)**: Procesado con `CSVLoader` y enviado al canal de memoria.
  - **Texto (`text/*`)**: Procesado con `TextLoader` y enviado al canal de memoria.
  - **Audio (`audio/*`)**: Encolado en `canal.sensorial.audio.crudo` para que `faster-whisper` lo procese (Lóbulo Temporal).
  - **Imagen (`image/*`)**: Encolado en `canal.sensorial.vision` para que la API de `LiteLLM` (Lóbulo Occipital) analice la imagen.

## Siguientes Pasos
- Comenzar con el **Plan de Implementación de la UI** (inyección de HTML, Monaco Editor, Xterm.js).

---

## Sesión: Panel Estilo LM Studio & Sistema de Notificaciones Amigables (Julio 2026)

### 4. Motor Local Llama.cpp & Panel Estilo LM Studio
- **[LlamaCppPanel.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Settings/LlamaCppPanel.tsx)**:
  - Navegador interactivo para seleccionar la carpeta base de binarios de `llama.cpp`.
  - Dashboard de telemetría en tiempo real: CPU, RAM, espacio en discos (SSD/HDD), VRAM (RTX 5060 Ti) y Temperatura GPU/CPU.
  - Generador dinámico de scripts de inicio rápido `.bat` guardados en `scripts/bats/`.
  - Control deslizable para MTP Speculative Decoding (`--spec-draft-n-max` de 1 a 10).
- **[gestor_llamacpp.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/gestor_llamacpp.py)**:
  - Módulo Python para el control de `llama-server.exe`, recolección de telemetría de hardware (`psutil`, `nvidia-smi`) y generación automática de `.bat`.

### 5. Sistema de Notificaciones, Banners y Guiado Amigable (UX/UI)
- **[useNotificationStore.ts](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/stores/useNotificationStore.ts)** & **[ToastContainer.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Notifications/ToastContainer.tsx)**:
  - Notificaciones flotantes animadas (Toasts) en la esquina inferior derecha con colores para Éxito 🟢, Error 🔴, Advertencia 🟡 e Información 🔵.
- **[Tooltip.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/UI/Tooltip.tsx)**:
  - Globitos flotantes explicativos al pasar el mouse sobre términos técnicos (`-ngl`, `-c`, `KV Cache`, `Flash Attention`, `MTP`).
- **[SidebarChat.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Sidebar/SidebarChat.tsx)**:
  - Muestra dinámica de **tokens por segundo (t/s)**, contador de tokens totales, porcentaje de **Ventana de Contexto** y caja desplegable para **Razonamiento** (`<think>`).

