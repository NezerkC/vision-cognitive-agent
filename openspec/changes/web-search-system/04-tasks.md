# SDD Tasks: Web Search System

**Change ID:** `web-search-system`
**Phase:** Tasks
**Depends on:** `03-design.md`
**Date:** 2026-07-14

---

## Task List

### Task 1: `WebSearchEngine` + `SearchCache` core classes

**File:** `cognitivo/skills/websearch_tool.py`

**Actions:**
1. Create `websearch_tool.py` with:
   - `@dataclass SearchResult` — title, url, snippet
   - `@dataclass SearchResponse` — status, results, source, error, timestamp
   - `@dataclass CacheEntry` — results, source, expires_at
   - `class SearchCache` — dict-based TTL cache with eviction
   - `class WebSearchEngine` — core class with `buscar()` method
2. Implement `_search_ddg()` — async DuckDuckGo via `DDGS.async_text()`
3. Implement `_search_tavily()` — async Tavily via `aiohttp`
4. Wire fallback chain: DDG → Tavily → error
5. Integrate cache: check before search, store after

**Verification:**
- `WebSearchEngine` instantiates without errors
- `SearchCache.get/set` works, TTL expiry works
- Module imports cleanly: `from skills.websearch_tool import WebSearchEngine`

---

### Task 2: `buscar_en_web` LangChain `@tool`

**File:** `cognitivo/skills/websearch_tool.py` (append)

**Actions:**
1. Add `@tool` decorator to `buscar_en_web(query, max_results=5)`
2. Instantiate `_engine = WebSearchEngine()` at module level
3. Return JSON string with results
4. Add descriptive docstring for LangChain discovery

**Verification:**
- `buscar_en_web("test query")` returns valid JSON string
- `from skills.websearch_tool import buscar_en_web` works
- Docstring describes the tool clearly in Spanish

---

### Task 3: `nodo_web` in LangGraph StateGraph

**File:** `cognitivo/orquestador_graph.py`

**Actions:**
1. Add `async def nodo_web(state: EstadoAgente) -> dict` function
2. Import and call `buscar_en_web` from skills
3. Append results to `vagones_informacion` as `{ estacion: "web", resultado }`
4. Handle mock mode (return simulated results)
5. Handle errors gracefully (log error, return error result in vagones)
6. Register `nodo_web` in graph: `workflow.add_node("nodo_web", nodo_web)`
7. Update `enrutador_estaciones` to handle `"web"` route → `"nodo_web"`
8. Add conditional edges from `nodo_web` to all other nodes

**Verification:**
- Graph compiles without errors
- Graph routes to `nodo_web` when `ruta_planeada` contains `"web"`
- Graph continues to `nodo_respuesta` after `nodo_web` completes

---

### Task 4: Planificador web keyword detection

**File:** `cognitivo/orquestador_graph.py`

**Actions:**
1. Add web detection block in `nodo_planificador`:
   ```python
   if any(k in text_lower for k in [
       "buscar", "internet", "web", "google", "investigar",
       "búsqueda", "busqueda", "qué es", "que es",
       "último", "actual", "noticias", "cómo hacer", "como hacer",
       "documentación", "documentacion", "tutorial",
       "última versión", "ultima version"
   ]):
       ruta.append("web")
   ```

**Verification:**
- Input "buscar documentación FastAPI" → ruta includes "web"
- Input "hola, ¿cómo estás?" → ruta does NOT include "web"
- Web route is added AFTER memoria in default path

---

### Task 5: `WebSearchDaemon` (broker daemon)

**File:** `cognitivo/web_search.py`

**Actions:**
1. Create `class WebSearchDaemon` following `protocolo_intriga.py` pattern:
   - `__init__(host, port, is_mock)`
   - `run()` — connect to broker, subscribe to `canal.web.busqueda` + `system`
   - `handle_search_request(data, writer)` — parse event, call engine, publish response
2. Publish results to `canal.web.resultado`
3. Handle system shutdown command
4. Add `if __name__ == "__main__":` entry point with `--mock` flag

**Verification:**
- Daemon connects to broker on start
- Receives search request → publishes result to `canal.web.resultado`
- Responds to `system` shutdown command

---

### Task 6: Watchdog registration

**File:** `core/main.py`

**Actions:**
1. Add `"web_search"` service entry in `BrainstemWatchdog.__init__` `self.services` dict:
   ```python
   "web_search": {
       "path": os.path.join(project_root, "cognitivo", "web_search.py"),
       "args": get_args("web_search", "web_search")
   }
   ```

**Verification:**
- Watchdog starts `web_search` daemon alongside other services
- `--mock` flag is respected

---

### Task 7: Mock mode in `arranque.yaml`

**File:** `config/arranque.yaml` (if exists)

**Actions:**
1. Add `web_search: false` (default mock off) to `modos_mock` section
2. If `arranque.yaml` doesn't exist or modos_mock section doesn't exist, skip

**Verification:**
- With `--mock` flag, WebSearchDaemon starts in mock mode
- Without `--mock` and `web_search: false` in config, daemon runs real searches

---

### Task 8: Tests

**File:** `core/test_web_search.py`

**Actions:**
1. Test `SearchCache`:
   - Test hit/miss
   - Test TTL expiry
   - Test max_size eviction (oldest removed)
2. Test `WebSearchEngine` with mocked DDG + Tavily:
   - Test DDG success path
   - Test DDG fail → Tavily fallback path
   - Test all fail → error result
3. Test `buscar_en_web` returns valid JSON
4. Test `nodo_web` with mocked engine:
   - Test graph routes to web and back

**Verification:**
- All tests pass: `pytest core/test_web_search.py -v`

---

## Effort Estimate

| Task | Files | Complexity | Est. Lines |
|------|-------|------------|------------|
| 1. Core engine + cache | 1 new | Medium | 120 |
| 2. @tool decorator | 1 new (append) | Low | 20 |
| 3. nodo_web graph node | 1 modified | Medium | 50 |
| 4. Planificador detection | 1 modified | Low | 15 |
| 5. WebSearchDaemon | 1 new | Medium | 100 |
| 6. Watchdog registration | 1 modified | Low | 5 |
| 7. arranque.yaml config | 1 modified | Low | 2 |
| 8. Tests | 1 new | Medium | 100 |
| **Total** | **5 new + 3 mod** | **Medium** | **~412** |

---

## Review Workload Forecast

- **Estimated changed lines:** ~412
- **400-line budget risk:** YES (412 > 400)
- **Decision needed before apply:** Ask user about splitting into chained PRs
