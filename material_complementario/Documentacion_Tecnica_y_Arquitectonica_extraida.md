
Documentación Maestra y Stack Tecnológico: Visión Studio / Visión OS
Este documento consolida de forma exhaustiva toda la arquitectura neuro-mimética, el stack de tecnologías, las librerías implementadas y la lógica de negocio estructurada para Visión Studio (el entorno gráfico IDE) y Visión OS (el núcleo cognitivo subyacente). Sirve como plano definitivo para continuar el desarrollo e interactuar con sistemas de IA colaboradores.

1. Arquitectura General y Filosofía del Sistema
Visión OS es un Sistema Operativo Cognitivo autónomo y local, diseñado bajo una arquitectura neuro-mimética. Se aleja de los asistentes de chat tradicionales para convertirse en un agente local (Enterprise/B2B) capaz de autogestionar su consumo de memoria y ejecución a través de simulación de "emociones" biológicas y homeostasis. Visión Studio es el Frontend IDE (nativo) que envuelve a este cerebro.

2. Stack Tecnológico del Frontend: Visión Studio (IDE)
El frontend ha evolucionado de inyecciones web básicas a una arquitectura nativa, robusta y rápida utilizando el ecosistema de Rust y Node.
Componente / Funcionalidad
Tecnología / Librería
Descripción Estratégica
 
Framework Core Nativo
Tauri (Rust) + React
Permite empaquetar la app web como binario de sistema operativo de alta velocidad. Se encarga de la comunicación Frontend-Backend mediante WebSockets y Sidecars.
Interfaz y Estructura
TypeScript + Vite + TailwindCSS
Layout estricto en CSS Grid (grid-cols-5) para los paneles laterales (20%), área central (60%) y herramientas (20%).
Editor de Código Base
@monaco-editor/react
Ofrece resaltado sintáctico, autocompletado y una experiencia visual de desarrollo idéntica a VS Code (Lóbulo de Escritura).
Terminal Integrada
xterm.js
Fundamental para visualizar la salida de comandos, logs del sistema operativo y ejecución de scripts.
Radar 3D (Memoria Visual)
Three.js / @react-three/fiber
Minimapa de memoria vectorial. Muestra en 3D cómo Visión conecta clústeres de información (SSD/HDD) en tiempo real.
Iconografía y UI Extra
lucide-react
Para componentes como FileTree.tsx y paneles UI estándar.

3. Stack Tecnológico del Backend: Visión OS (Core Cognitivo)
El backend se construye en Python como un "Tauri Sidecar", orquestando todo el razonamiento, almacenamiento y ejecución mediante una API robusta y grafos de estado multiagente.
Componente Anatómico
Tecnología / Librería
Rol en la Arquitectura
 
Servidor Principal / Tronco Cerebral
FastAPI (Python)
Motor backend que recibe peticiones del frontend Tauri. Expondrá endpoints HTTP y WebSockets para el streaming de pensamientos.
Lóbulo Temporal (Memoria Vectorial)
LanceDB + embeddings locales
Base de datos vectorial local. Estructura de indexación híbrida y Cuantización de Producto (PQ) para manejar millones de recuerdos sin agotar la RAM.
Lóbulo Frontal (Enrutamiento/Razonamiento)
LangGraph + LiteLLM
Reemplaza la lógica lineal por un grafo de estados cíclicos. Enruta dinámicamente tareas a modelos locales (Ollama/Llama 3) o APIs premium (GPT-4o/Claude).
Colaboradores / Enjambre (Workspaces)
CrewAI / Swarm
Agentes especializados (Ej. Agente Archivista, Agente Analista) con herramientas MCP específicas bajo el mando de Visión.
Introspección (Reducción Dimensional)
UMAP-learn, Scikit-learn (PCA), Pandas
Reduce los embeddings de 512+ dimensiones a 3/4 dimensiones (X, Y, Z, W) para ser procesados por el Radar 3D (Three.js) del Frontend.
Inferencia e Inteligencia (Modelos)
Torch, Transformers, Ollama, CLIP
Carga de modelos NLP (texto) y visión artificial computacional para comprender el entorno local.

4. Mecanismos Biológico-Cognitivos (Business Logic)
La verdadera inteligencia de Visión recae en sus protocolos no lineales programados a través de archivos JSON y YAML.
Hemisferio Izquierdo (Estructural): Motor determinista para la escritura de código, seguimiento de procesos estrictos y herramientas MCP.
Hemisferio Derecho (Emocional/Holístico): Modula el comportamiento basado en el contexto y estado general (Homeostasis).
Rueda de Emociones (Plutchik): Gestionado en config/emociones.json con 4 ejes polares (-1.0 a 1.0). Ejemplo: Alegría vs Tristeza regula el consumo de tokens y la verbosidad; Ira vs Miedo regula el nivel de escrutinio de seguridad de código.
Protocolo de Intriga (Curiosidad Orgánica): Basado en distancias euclidianas. Cuando el sistema detecta un "espacio vacío" en la densidad de LanceDB, activa agentes en segundo plano para investigar en la web o consultar documentaciones, rellenando el conocimiento de forma proactiva.
Búsqueda Híbrida con RRF: Combina búsqueda semántica (vectores) con búsqueda Full-Text exacta para garantizar precisión Enterprise (Reciprocal Rank Fusion).

5. Estructura de Directorios Recomendada
/VisionOS_Project├── /vision_studio (Frontend)│   ├── package.json (Vite + React + Tailwind + Monaco + Three.js)│   ├── /src│   │   ├── /components│   │   │   ├── /Sidebar (FileTree.tsx, EmotionState.tsx)│   │   │   ├── /Editor (Monaco setup)│   │   │   ├── /Terminal (Xterm setup)│   │   │   └── /Radar3D (Three.js/Fiber)│   ├── /src-tauri│   │   ├── tauri.conf.json (Configuración de Sidecar FastAPI)│   │   └── src/main.rs (Punto de entrada de Rust)├── /backend (Core Python / FastAPI)│   ├── requirements.txt (lancedb, fastapi, langgraph, crewai, umap-learn...)│   ├── /memoria (.lancedb index storage)│   ├── /config (emociones.json, permisos.yaml)│   ├── /scripts (percepcion.py, cerebro.py, llm_router.py)│   ├── /datos_crudos (Para ingestión de PDFs/Docs)│   └── /notebooks (Para pruebas de mapas mentales 2D con Matplotlib)  

6. Rutas Prácticas para Próximos Desarrollos
Pipeline de Carga Diferida (Lazy Loading) Frontend: Aplicar React.lazy a Monaco Editor y Three.js para asegurar un renderizado inicial del IDE inferior a 10ms.
Integración Sidecar: Compilar el backend FastAPI mediante PyInstaller e integrarlo en Tauri para un ciclo de vida unificado (evitando fugas de memoria por procesos huérfanos).
Grafo de Estados con LangGraph: Migrar el router lineal actual (llm_router.py) a un sistema cíclico, habilitando bucles reales de retroalimentación para el Protocolo de Intriga.