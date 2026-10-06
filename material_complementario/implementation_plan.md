# Implementation Plan - Visión OS / Studio Core Modules Integration

Implement the key missing core modules of **Visión OS / Visión Studio**: 4D Vector Memory & Storage Tiering (Cerebelo), Sleep/Wake Cycle Daemon (Glándula Pineal), Active Window Intrigue & Tavily Web Search Protocol, and Real-time Telemetry WebSocket connection for Tauri (Visión Studio).

## User Review Required

> [!IMPORTANT]
> **Scope Kickoff & Conventional Commit Classification**: Per project rules, we must classify this delivery (e.g., `feat`, `refactor`, `chore`). We recommend setting this branch as `feat/core-cognitive-modules` with `feat:` commit prefix.

> [!NOTE]
> All code changes, comments, and identifiers will strictly adhere to English defaults while user-facing responses follow Rioplatense Spanish per workspace directives.

## Open Questions

> [!IMPORTANT]
> 1. **Delivery Classification**: Is this delivery classified as `feat` (Feature delivery for missing core modules)? (Branch: `feat/core-cognitive-modules`)

## Proposed Changes

---

### Módulo Cerebelo y Memoria Vectorial 4D (`cognitivo/` & `memoria/`)

#### [NEW] [memoria.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/memoria.py)
- Create `cognitivo/memoria.py` exposing clean high-level interfaces for the Cerebellum 4D Memory engine.
- Implement 4D distance metric logic $D^2 = X^2 + Y^2 + Z^2 + W^2$ combining 3D latent coordinates $(X,Y,Z)$ and emotional/intrigue factor $(W)$.

#### [MODIFY] [lancedb_manager.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/memoria/lancedb_manager.py)
- Update LanceDB schema to support explicit 4D spatial vector metadata and storage tiering.
- Implement Hot/Cold Storage Tiering:
  - **Hot Tier (SSD/RAM - `memoria_activa`)**: HNSW index for recent entries and high-W memories.
  - **Cold Tier (HDD/Archive - `memoria_historica`)**: PQ (Product Quantization) index for compressed archival storage.
- Refactor LanceDB search to perform true Hybrid Search (Vector Dense Search + Tantivy FTS) with Reciprocal Rank Fusion (RRF):
  $$RRF(d) = \frac{1}{k + r_{vec}(d)} + \frac{1}{k + r_{fts}(d)}, \quad k=60$$

---

### Daemon Glándula Pineal (`daemons/`)

#### [NEW] [pineal_daemon.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/daemons/pineal_daemon.py)
- Create `daemons/pineal_daemon.py` to handle the system wake/sleep idle cycle.
- Implement background async tasks for system idle periods:
  1. Context summary generation (consolidating daily events).
  2. Short-term memory consolidation (moving items from Hot to Cold tier based on decay/W-factor).
  3. Nocturnal GraphRAG graph indexing.

---

### Búsqueda Web y Protocolo de Intriga (`cognitivo/` & `config/`)

#### [MODIFY] [web_search.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/web_search.py)
#### [MODIFY] [websearch_tool.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/skills/websearch_tool.py)
- Ensure direct integration with Tavily API (`TAVILY_API_KEY` from `.env`).
- Provide automatic fallback chain: DDGS → Tavily → Mock.

#### [MODIFY] [hardware_interfaces.json](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/config/hardware_interfaces.json)
#### [MODIFY] [protocolo_intriga.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/protocolo_intriga.py)
- Add active window change / screen error event triggers in `hardware_interfaces.json`.
- Formulate intelligent search queries on active window change / error detection after user authorization via HITL mental ticket.

---

### Frontend IDE & Sidecar WebSockets (`sentidos/` & `vision_studio/`)

#### [MODIFY] [sistema_periferico.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/sentidos/sistema_periferico.py)
- Expand WebSocket broadcast loop to push real-time telemetry:
  - System hardware metrics (RTX 5060 Ti GPU VRAM/load, RAM usage).
  - Plutchik Emotion Wheel state updates.
  - 4D vector memory node point clouds for 3D latent radar.

#### [NEW] [useWebSocketTelemetry.ts](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/stores/useWebSocketTelemetry.ts)
#### [MODIFY] [Radar3D.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Memory/Radar3D.tsx)
#### [MODIFY] [StatusBar.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Layout/StatusBar.tsx)
- Connect Tauri frontend via WebSockets to FastAPI Sidecar (`ws://127.0.0.1:8000/ws`).
- Display live GPU/RAM telemetry in `StatusBar`.
- Render live 4D memory spatial nodes in `Radar3D`.

---

## Verification Plan

### Automated Tests
- Run full Pytest test suite: `pytest tests/`
- Run Ruff lint checks: `ruff check core/ cognitivo/ sentidos/ memoria/ tests/`

### Manual Verification
- Test 4D metric and RRF search ranking in LanceDB.
- Run `daemons/pineal_daemon.py` in standalone test mode to verify async idle consolidation.
- Test Tavily API web search integration and active window intrigue ticket triggering.
- Launch sidecar and verify WebSocket telemetry stream in `vision_studio` Tauri frontend.
