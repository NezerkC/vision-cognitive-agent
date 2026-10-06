# Plan de Arquitectura e Implementación: Agentes Entrelazadores de Lóbulos, Acciones e Información (Vision OS / Vision Studio)

## Contexto y Visión Arquitectónica

En **Vision OS**, un Agente no es simplemente un prompt con herramientas; es un **orquestador dinámico** que entrelaza los diferentes **Lóbulos Cognitivos** del sistema:
- **Lóbulo Parietal (Memoria Vectorial / RAG):** LanceDB y contexto histórico.
- **Lóbulo Frontal (Decisión y Enrutado LLM):** LangGraph y `LLMRouter`.
- **Hemisferio Izquierdo (Ejecución y Herramientas):** Terminal sandboxed, llamadas al sistema y scripts.
- **Sentidos (Ingreso / Egreso):** Búsqueda Web (Tavily/DuckDuckGo), audio, inspección visual.
- **Lóbulo Temporal (Logs y EventBroker):** Monitoreo de homeostasis y eventos TCP.

### Niveles de Complejidad Adaptativa:
1. **Agentes Simples / Directos (Express ⚡):** Ejecutan una acción puntual en un solo lóbulo sin planificación pesada (ej: consulta rápida a RAG o ejecutor directo).
2. **Agentes Complejos / Entrelazadores (Deep Graph 🕸️):** Construyen una red de dependencia dinámica entre lóbulos (ej: Memoria ➔ Búsqueda Web ➔ Sandbox Terminal ➔ Verificación ➔ Respuesta).

---

## Visualización KANBAN del Plan de Agentes

El módulo de Agentes renderizará el plan de trabajo mediante un **Tablero Kanban Interactivo** dividido por **Estados/Lóbulos de Trabajo**:

| Columna | Propósito y Contenido |
| :--- | :--- |
| 📋 **Backlog / Pendientes** | Tareas en cola enviadas al sistema por el usuario o disparadores automáticos. |
| 🧠 **Planificación (Lóbulo Frontal)** | Agentes desglosando la tarea en sub-pasos y evaluando la ruta óptima. |
| ⚡ **En Ejecución (Lóbulos Activos)** | Acciones corriendo en tiempo real (Lóbulo Parietal/Memoria, Sentidos/Web, Hemisferio Izquierdo/Terminal). |
| 🔍 **Verificación y Síntesis** | Agentes validando los outputs de la ejecución antes de darlos por concluidos. |
| ✅ **Completado** | Acciones finalizadas con sus respectivos vagones de información (payloads) adjuntos. |

### Tarjetas del Kanban:
- **Etiquetas de Complejidad:** Badge visual `[Express]` o `[Entrelazado]`.
- **Lóbulo Asignado:** Icono y color del lóbulo a cargo de la tarjeta.
- **Inspector de Payload:** Expandible para ver qué datos ("vagón de información") lleva la tarea.

---

## Cambios Propuestos

### 1. Backend Cognitivo (Python)
- **`cognitivo/orquestador_graph.py`:**
  - Exponer un esquema tipado `AgentKanbanTask` para representar las tareas en columnas (`pending`, `planning`, `in_progress`, `verifying`, `completed`).
  - Emitir eventos de cambio de columna en tiempo real vía `EventBroker` / WebSockets.
- **`cognitivo/distrito_agentes/`:**
  - Definir tareas con etiquetas de complejidad (`Express` vs `Entrelazado`).

### 2. Frontend IDE (`vision_studio`)
- **`src/stores/useSettingsStore.ts`:**
  - Añadir pestaña `'agents'` a `activeSidebarTab` para navegación en `ActivityBar`.
- **`src/components/Layout/ActivityBar.tsx`:**
  - Agregar botón con icono de red/nodos o Kanban (`Bot` / `Kanban`) para acceder a la vista de Agentes.
- **`src/components/Sidebar/SidebarComponents.tsx`:**
  - Registrar el caso `'agents'` en la vista lateral/explorador o vista principal.
- **`src/components/Agents/AgentsKanbanView.tsx` [NUEVO]:**
  - Componente completo de Tablero Kanban interactivo.
  - Columnas de Lóbulos/Estados.
  - Tarjetas drag-and-drop o de monitoreo activo en tiempo real.
  - Filtro por complejidad (*Solo Express*, *Solo Entrelazados*, *Todos*).

---

## Plan de Verificación

### Pruebas Automatizadas
- `pytest tests/test_orquestador_graph.py`: Verificar que las tareas expongan los estados correctos para el Kanban.
- `cd vision_studio && npx tsc --noEmit`: Asegurar tipado TypeScript limpio en el frontend.

### Verificación Manual
- Navegar a la sección **Agentes** en `vision_studio`.
- Verificar que las columnas Kanban (Backlog, Planificación, En Ejecución, Verificación, Completado) rendericen correctamente y reaccionen al estado de las tareas.
