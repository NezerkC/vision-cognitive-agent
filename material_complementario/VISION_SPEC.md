# VISION OS: TECHNICAL SPECIFICATION & ARCHITECTURE DOCUMENT (v2.0)

## 1. System Overview
Vision OS is a local, Edge AI autonomous agent designed for maximum data sovereignty, resource efficiency, and local execution. The system acts as a specialized DevOps/Development co-engineer, featuring continuous environment awareness, multimodal ingestion, and dynamic emotional state routing.

**Core Tech Stack:**
- **Backend/Orchestration:** Python, LangGraph (StateGraph), FastAPI.
- **Vector Database:** LanceDB (Embedded, local).
- **LLM Routing:** LiteLLM (Dynamic routing between local models like Llama3/Phi3 and external APIs).
- **Frontend:** Tauri + React/Vanilla JS, Monaco Editor, Xterm.js, Three.js.
- **Sensory Inputs:** `mss` (screen capture), `faster-whisper` (STT), `psutil` (Host Mapping), local TTS, OpenCV (Webcam/Phone Link via DirectShow).

---

## 2. Memory Architecture: 4D Vector Space & Hybrid Search

The storage layer is a continuous, interactable mathematical space. 

### 2.1 Indexing & Tiering (Hot/Cold Data)
- **Hot Memory (SSD):** Indexed using **HNSW** for low-latency retrieval of frequent or recent data.
- **Cold Memory (HDD):** Archival storage using **IVF-PQ (Product Quantization)** to minimize RAM footprint.

### 2.2 4D Spatial Mapping
Embeddings are mapped into a 4-dimensional representation:
- **[X, Y, Z]:** Calculated via Euclidean Distance. Determines the spatial positioning of the vector cluster for the frontend 3D radar.
- **[W] (Metadata Dimension):** Stores system-critical variables evaluated via Cosine Similarity. Includes `temperature` (access frequency), `timestamp`, and `emotion_weight`.

### 2.3 Retrieval Strategy: Progressive RAG & RRF
To prevent hallucinations and guarantee exact code retrieval:
1. **Reciprocal Rank Fusion (RRF):** Queries execute semantic search (dense vectors) and keyword search (sparse/BM25) simultaneously, merging results via RRF.
2. **Progressive Relaxation Algorithm:** Starts with Top_K=1 (Exact match). If it fails, LangGraph loops back, increasing `Top_K += 1` and lowering the similarity threshold iteratively (max 10 retries).

---

## 3. Orchestration & State Management (LangGraph "Information Train")

Vision OS uses a `StateGraph` architecture. The core routing is no longer linear but acts as an "Information Train" accumulating data across specialized nodes.

### 3.1 State Dictionary (`EstadoAgente`)
The graph maintains an asynchronous state passing through nodes:
- `input_usuario`: str
- `ruta_planeada`: list[str] (Populated by the Orchestrator node).
- `vagones_informacion`: Annotated[list, operator.add] (Accumulates data from nodes without overwriting).
- `respuesta_final`: str

### 3.2 Dynamic Routing & Emotional Plasticity
- **Homeostasis:** LLM calls are routed based on task complexity and system state (`config/emociones.json`).
- **Pre-filtering:** Before querying LanceDB, metadata is hard-filtered by the current emotion.
- **Emotional Learning:** The final response node has access to an `actualizar_emocion` Tool. The LLM can dynamically rewrite `emotions.json` based on the interaction's outcome, enabling emotional plasticity while keeping `permissions.json` immutable.

### 3.3 The Intrigue Protocol & Self-Training ("Zapatilla Eléctrica")
Error handling and skill acquisition are active.
1. **Host Mapping:** The Right Hemisphere uses `psutil` and `os` to scan the host environment for installed CLIs/Tools (e.g., Docker, Git).
2. **Capacitation Trigger:** If an unknown tool is detected, it triggers the Intrigue Protocol with `mode="capacitacion"`.
3. **Autonomous Resolution:** The agent searches the web (Tavily) for documentation, dynamically writes a Python script wrapped in a LangChain `@tool` decorator, and saves it in `cognitivo/skills/` for future use.

---

## 4. Multimodal Ingestion Port

The Peripheral System (FastAPI running within the existing `asyncio` event loop) exposes a unified learning endpoint (`POST /api/memoria/aprender`).

**MIME Type Router:**
- **Text/PDF/CSV:** Processed via LangChain DocumentLoaders and `RecursiveCharacterTextSplitter`.
- **Audio:** Transcribed asynchronously using local `faster-whisper`, then indexed.
- **Image/Video:** Processed via the Occipital Lobe (Local VLM like Qwen3-VL/LLaVA) to generate detailed semantic descriptions, which are stored in LanceDB alongside the original file path.

---

## 5. Identity & Creator Recognition

Vision OS is aware of its operator. 
- **`config/personalidad.yaml`:** Contains the master System Prompt identifying the current user as the "Architect and Creator". 
- Vision assumes the persona of an autonomous co-engineer, maintaining a collaborative rather than purely subservient dynamic.

---

## 6. UI/UX: Vision Studio Frontend (IDE Cognitive Interface)

The frontend (Tauri) is designed for engineering productivity, shifting away from a simple chatbot UI to a full IDE layout.

- **Main View (Center):** Houses **Monaco Editor** for code manipulation, tightly integrated with the chat and LangGraph thought streaming.
- **Terminal View (Bottom):** Houses **Xterm.js** rendering the actual sandboxed terminal executions.
- **3D Radar (Side Panel):** The Three.js LanceDB visualization is minimized to a side widget ("Memory Radar") that emits subtle flashes during vector retrieval. 
- **Audit Mode:** The 3D radar can be expanded to fullscreen via settings for deep vector auditing.
- **Hardware Toggles:** UI controls map directly to backend Python threads (e.g., a physical toggle to pause `PyAudio` listening).

---

## 7. System Directory Structure

```text
VisionOS/
├── memoria/            # LanceDB instances (.lancedb) [Hot/Cold tiering]
├── config/             
│   ├── emociones.json  # Plutchik wheel parameters & Homeostasis state
│   ├── permisos.json   # HITL rules, directory access boundaries
│   └── personalidad.yaml # Creator identity and core System Prompt
├── cognitivo/
│   ├── orquestador_graph.py # LangGraph StateGraph (Information Train)
│   ├── llm_router.py   # LiteLLM dynamic router & cost manager
│   ├── ejecutor_izquierdo.py # Sandbox/Tool execution
│   └── contexto_derecho.py # Host mapping (Zapatilla Eléctrica)
├── sentidos/
│   ├── sistema_periferico.py # FastAPI Webhooks & Multimodal Learning Port
│   ├── vision_parietal.py # mss Screen Capture & Camera (DirectShow support)
│   └── oido_parietal.py # PyAudio + Whisper
├── ui/                 # Tauri Frontend (Monaco, Xterm.js, Three.js)
├── datos_crudos/       # Temporary ingestion folder (File Loaders)
└── VISION_SPEC.md      # Master Architecture Document

```

---

**END OF SPECIFICATION.** **Note to AI Assistant:** When instructed to implement a specific feature, refer to this document for architectural constraints, naming conventions, and methodologies.
