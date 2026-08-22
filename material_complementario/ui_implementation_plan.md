# [VISIÓN OS 2.0] Frontend IDE (Tauri + React) Implementation Plan

Este documento detalla el plan de implementación para la **FASE 8**, donde construimos **Visión Studio**, el IDE cognitivo nativo utilizando Tauri, React, y Tailwind CSS. Esto reemplaza el plan anterior basado en inyección HTML plana.

## User Decisions Recorded

> [!IMPORTANT]
> - **Stack Definitivo:** Se abandona la inyección HTML/JS básica (`gui/`) a favor de una arquitectura nativa de alto rendimiento: **Tauri (Rust) + React (TypeScript + Vite) + TailwindCSS**.
> - **Layout:** Se utilizará un layout estricto en **CSS Grid (`grid-cols-5`)** dividiendo el viewport en 20% (Izquierda), 60% (Centro), 20% (Derecha).
> - **Componentes IDE:** Se integrarán librerías profesionales (`@monaco-editor/react`, `xterm`, `@react-three/fiber`) dentro de contenedores modulares.

## Proposed Changes

Vamos a encapsular cada bloque lógico en su propio componente de React para mantener `App.tsx` limpio y escalable. Todo se trabajará dentro del directorio `vision_studio/src/`.

---

### 1. Panel Izquierdo: Controles y Estado (`src/components/Sidebar/`)
- **[NEW] [FileTree.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Sidebar/FileTree.tsx)**: Componente UI para mostrar el árbol del workspace local usando `lucide-react`.
- **[NEW] [ChatHistory.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Sidebar/ChatHistory.tsx)**: Lista de interacciones recientes.
- **[NEW] [EmotionState.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Sidebar/EmotionState.tsx)**: Representación visual del archivo `emociones.json` (Plutchik) conectándose al backend mediante Axios.

### 2. Área Central Superior: Editor y Chat (`src/components/Editor/`)
- **[NEW] [CognitiveEditor.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Editor/CognitiveEditor.tsx)**:
  - Implementación de `<Editor />` de `@monaco-editor/react`.
  - Soporte de sintaxis para Python y JSON, con tema oscuro personalizado (`vs-dark`).
- **[NEW] [ChatOverlay.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Editor/ChatOverlay.tsx)**:
  - Interfaz flotante o adyacente para el Thought Streaming de LangGraph.

### 3. Área Central Inferior: Sandbox Terminal (`src/components/Terminal/`)
- **[NEW] [IntegratedTerminal.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Terminal/IntegratedTerminal.tsx)**:
  - Inicialización de `Terminal` de `xterm.js` con el addon `xterm-addon-fit` para que se ajuste automáticamente al contenedor (30% de alto).
  - Escuchará WebSockets o APIs del "Hemisferio Izquierdo" para mostrar el `stdout` del entorno Docker/Sandbox local.

### 4. Panel Derecho: Radar de Memoria 4D (`src/components/Memory/`)
- **[NEW] [Radar3D.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Memory/Radar3D.tsx)**:
  - Lienzo `<Canvas>` de `@react-three/fiber` renderizando un entorno tridimensional (grilla, ejes).
  - Mapeo de vectores 4D (X, Y, Z, W) como `InstancedMesh` de Three.js para visualizar los datos de LanceDB.

### 5. Ensamblaje Final en Layout (`src/App.tsx`)
#### [MODIFY] [App.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/App.tsx)
- Reemplazar los "placeholders text" actuales por los nuevos componentes importados.

## Optimizaciones Arquitectónicas (Aprobadas)
1. **Zustand para Estado de Alta Frecuencia:** Se evitarán los re-renders innecesarios. Las mutaciones 3D en Radar3D se harán vía `useRef` en el `useFrame` de react-three-fiber, sin estados de React.
2. **Lazy Loading de Componentes Pesados:** Monaco y Three.js se cargarán usando `React.lazy` y `Suspense` para asegurar que la app abra en milisegundos.
3. **Paneles Dinámicos:** Se implementó `react-resizable-panels` en `App.tsx` para permitir que los usuarios colapsen y redimensionen los paneles.
4. **Buffering en Xterm.js:** Se implementará un acumulador de strings (búfer vaciado cada 50ms) para evitar congelamientos del DOM si LangGraph arroja mucha data.
5. **Tauri Sidecar:** En fases avanzadas, FastAPI se empaquetará con PyInstaller para que Tauri maneje su ciclo de vida como sidecar.

## Verification Plan

### Automated Tests
- Al no haber lógica de testing de frontend configurada aún, la verificación principal será visual y funcional.

### Manual Verification
1. Compilar y correr el frontend nativo con `npm run tauri dev`.
2. Verificar que los 3 componentes pesados (Monaco, Xterm, Three.js) se rendericen sin romper el CSS Grid de Tailwind.
3. Verificar que redimensionar la ventana gatille `fit()` en Xterm y reacomode el canvas 3D adecuadamente.
