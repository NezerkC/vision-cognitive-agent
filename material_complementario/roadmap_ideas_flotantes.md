# 🚀 Roadmap y Banco de Ideas Flotantes (Vision OS / Vision Studio)

Este documento centraliza todas las ideas, conceptos arquitectónicos y funcionalidades "en el aire" que hemos ido charlando y que forman parte de la visión a futuro del proyecto, para que no se pierdan.

---

## 1. Code Graph / Call Graph Interactivo (Contexto Visual)
**Estado:** 💡 Idea Flotante
**Objetivo:** Proveer un mapa mental del código tanto para el desarrollador humano como para el agente cognitivo.

*   **Para el Developer (DX):** Implementar un panel visual (usando librerías como `React Flow`, `D3` o `Cytoscape`) que dibuje nodos (funciones, clases, archivos) y aristas (quién llama a quién, dependencias). Permitirá navegar el proyecto haciendo clic en un nodo para abrir el código exacto. Evita la ceguera de arquitectura en proyectos masivos.
*   **Para el Agente Cognitivo:** El backend (Rust o Python) se encargará de parsear el AST (Abstract Syntax Tree) de los proyectos y mantener este grafo. El agente podrá "recorrer" el grafo lógicamente para entender impactos de refactorización sin tener que leer archivos de texto plano a fuerza bruta.

## 2. Radar de Memoria 3D (Lóbulo Parietal Visual)
**Estado:** 🏗️ En Visión (VISION_SPEC)
**Objetivo:** Tangibilizar el trabajo de la base de datos vectorial (LanceDB).

*   **Widget Lateral:** Un panel en la UI construido con `Three.js` que represente el espacio vectorial matemático de 4D donde "vive" la memoria de Vision.
*   **Feedback Visual:** El radar emitirá destellos o señales visuales en tiempo real cuando el sistema esté haciendo una recuperación de memoria (RAG), dándole al usuario feedback orgánico de que el agente está "recordando".

## 3. Integración Plena de Herramientas IDE
**Estado:** 🏗️ En Progreso
**Objetivo:** Consolidar `vision_studio` como un IDE completo, alejándolo del formato clásico de "chatbot".

*   **Editor (Monaco):** Sincronización profunda del editor de código donde el agente pueda streamear sus pensamientos o sugerencias directamente como comentarios o diffs en línea.
*   **Terminal (Xterm.js):** Consola sandboxed conectada directo al Hemisferio Izquierdo del backend, permitiendo ver en tiempo real cómo el agente ejecuta comandos.

## 4. Plasticidad Emocional y "Protocolo de Intriga"
**Estado:** 🏗️ En Visión (VISION_SPEC)
**Objetivo:** Autonomía pura en la resolución de problemas.

*   **Capacitación Autónoma (Zapatilla Eléctrica):** Si el agente detecta un CLI o herramienta en el host del usuario que no sabe usar, se activa el modo capacitación: investiga en Tavily, programa su propio script (wrapper de LangChain) y lo guarda para saber usarlo en el futuro.
*   **UI Reactiva:** La interfaz de `vision_studio` debe reflejar sutilmente el estado de "homeostasis" o nivel de esfuerzo del agente (ej: cambios de color, indicadores de "pensamiento profundo").

---
*Nota: Este documento se actualizará a medida que surjan nuevas ideas o cuando decidamos planificar e implementar alguna de ellas.*
