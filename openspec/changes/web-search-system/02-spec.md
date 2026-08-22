# SDD Spec: Web Search System

**Change ID:** `web-search-system`
**Phase:** Spec
**Depends on:** `01-proposal.md`
**Date:** 2026-07-14

---

## 1. Glossary

| Term | Definition |
|------|------------|
| **DDG** | DuckDuckGo — primary search backend (free, no API key) |
| **Tavily** | Secondary search backend (structured results, requires API key) |
| **Skill** | LangChain `@tool`-decorated function in `cognitivo/skills/` |
| **Graph Node** | A station in the LangGraph StateGraph (`nodo_web`) |
| **Result Envelope** | Standardized JSON structure returned by all search operations |
| **TTL** | Time-to-live for in-memory search cache |

---

## 2. Functional Requirements

### FR-01: Web Search Skill

The system MUST provide a LangChain `@tool`-decorated function `buscar_en_web` in `cognitivo/skills/websearch_tool.py` that:

| # | Requirement |
|---|-------------|
| FR-01.1 | Accept a `query: str` parameter |
| FR-01.2 | Accept an optional `max_results: int` parameter (default: 5) |
| FR-01.3 | Return a list of results, each with `title`, `url`, `snippet` |
| FR-01.4 | Include a `source` field indicating which backend served the result |
| FR-01.5 | Include a `status` field: `"success"`, `"error"`, or `"no_results"` |
| FR-01.6 | Have a clear docstring for LangChain tool discovery |

### FR-02: Search Backend Chain

The search MUST try backends in order with fallback:

```
DDG.async_search() → success? Return results
    ↓ on failure/empty
Tavily.search() → success? Return results
    ↓ on failure/no key
Mock → Return simulated results
```

| # | Requirement |
|---|-------------|
| FR-02.1 | DuckDuckGo is always attempted first |
| FR-02.2 | If DDG returns results, return immediately (do NOT call Tavily) |
| FR-02.3 | If DDG fails (exception or empty results), attempt Tavily |
| FR-02.4 | Tavily is only called if `TAVILY_API_KEY` is set |
| FR-02.5 | If all backends fail, return `status: "error"` with message |
| FR-02.6 | Each backend call has an 8-second timeout |

### FR-03: Graph Node `nodo_web`

The LangGraph StateGraph in `orquestador_graph.py` MUST include a `nodo_web` station that:

| # | Requirement |
|---|-------------|
| FR-03.1 | Takes `input_usuario` from state and determines if web search is needed |
| FR-03.2 | Calls the `buscar_en_web` skill internally |
| FR-03.3 | Appends results to `vagones_informacion` as `{ estacion: "web", resultado: [...] }` |
| FR-03.4 | Does NOT block the graph — respects configured timeout |
| FR-03.5 | Routes back to planificador for further stations or directly to respuesta |

### FR-04: Planificador Auto-Detection

The planificador node MUST detect when web search is needed:

| # | Requirement |
|---|-------------|
| FR-04.1 | Detect keywords: `"buscar"`, `"internet"`, `"web"`, `"googlear"`, `"investigar"`, `"busqueda"`, `"qué es"`, `"último"`, `"actual"`, `"noticias"`, `"cómo"` + `"hacer"` |
| FR-04.2 | Add `"web"` to `ruta_planeada` when detection triggers |
| FR-04.3 | Web station runs after memoria but before respuesta in the default path |

### FR-05: Event Broker Topic `canal.web.busqueda`

Any daemon MUST be able to search the web by publishing to this topic:

| # | Requirement |
|---|-------------|
| FR-05.1 | Subscribe to `canal.web.busqueda` and listen for `action: "search"` events |
| FR-05.2 | Event format: `{ request_id, query, max_results?, timeout? }` |
| FR-05.3 | Publish results to `canal.web.resultado` with matching `request_id` |
| FR-05.4 | Result format: `{ request_id, status, results: [...], source, timestamp }` |

### FR-06: In-Memory Cache

| # | Requirement |
|---|-------------|
| FR-06.1 | Cache search results by query in a dict |
| FR-06.2 | TTL: 5 minutes per cached entry |
| FR-06.3 | Cache is per-process (daemon-level, not shared across daemons) |
| FR-06.4 | Cache respects `max_results` — different counts are separate entries |

---

## 3. Non-Functional Requirements

| # | Requirement | Target |
|---|-------------|--------|
| NFR-01 | Max search latency (DDG) | < 4s p95 |
| NFR-02 | Max search latency (Tavily) | < 6s p95 |
| NFR-03 | Total fallback chain timeout | < 18s (DDG 8s + Tavily 8s + overhead) |
| NFR-04 | Zero new pip dependencies | `duckduckgo_search` is already installed |
| NFR-05 | Cache hit response | < 50ms |
| NFR-06 | All async, non-blocking | asyncio throughout |

---

## 4. Event Contracts

### 4.1 Search Request (`canal.web.busqueda`)

```json
{
  "request_id": "web-search-1712345678",
  "query": "how to install litellm",
  "max_results": 5
}
```

### 4.2 Search Response (`canal.web.resultado`)

```json
{
  "request_id": "web-search-1712345678",
  "status": "success",
  "source": "duckduckgo",
  "results": [
    {
      "title": "GitHub - BerriAI/litellm",
      "url": "https://github.com/BerriAI/litellm",
      "snippet": "Call all LLM APIs using the OpenAI format..."
    }
  ],
  "error": null,
  "timestamp": 1712345678.123
}
```

---

## 5. Scenarios

### Scenario 1: Happy path — DDG returns results

```
Input: "buscar documentación de FastAPI"
Planificador detects "buscar" → adds "web" to ruta_planeada
nodo_web calls buscar_en_web("documentación de FastAPI")
  → DDG returns 5 results
  → Results appended to vagones_informacion
nodo_respuesta synthesizes final answer with search context
Expected: Response includes FastAPI documentation links
```

### Scenario 2: DDG fails, Tavily fallback with key

```
Input: "últimas noticias IA 2026"
DDG.async_search() raises RateLimitException
TAVILY_API_KEY is set → call Tavily
  → Tavily returns 3 structured results
nodo_web returns results with source: "tavily"
Expected: Response uses Tavily results, system logs the DDG failure
```

### Scenario 3: All backends fail

```
Input: "investigar error X"
DDG fails, no TAVILY_API_KEY, mock mode disabled
buscar_en_web returns status: "error", results: []
nodo_web adds vagones_informacion with empty results
nodo_respuesta: "No se pudo obtener información de internet"
Expected: Graceful degradation, system continues without crashing
```

### Scenario 4: Direct Event Broker call

```
Daemon publishes to canal.web.busqueda: { request_id: "my-search-1", query: "python async", max_results: 3 }
Web search daemon receives event, performs search
Publishes to canal.web.resultado: { request_id: "my-search-1", ...results }
Original daemon receives response via its subscription
Expected: Any daemon can search without going through the graph
```

### Scenario 5: Cache hit

```
First call: buscar_en_web("python asyncio") → DDG search → stores in cache
Second call (within 5 min): buscar_en_web("python asyncio") → returns cached results
Expected: Second call returns instantly (< 50ms), no DDG call made
```

---

## 6. File Structure (Delta)

```
cognitivo/
  skills/
    websearch_tool.py        NEW — @tool decorated function + cache + backends
  orquestador_graph.py       MODIFIED — add nodo_web + update planificador + enrutador
  protocolo_intriga.py       MODIFIED (optional) — use websearch_tool instead of direct Tavily call
```

No changes needed to `core/`, `sentidos/`, `memoria/`, or `config/`.

---

## 7. Dependencies

| Dependency | Status | Used For |
|------------|--------|----------|
| `duckduckgo_search` | ✅ Already in requirements.txt | Primary search backend |
| `aiohttp` | ✅ Already in requirements.txt | HTTP calls for Tavily |
| `tavily` | ❌ Not installed — use direct HTTP via aiohttp instead | Avoids new dependency |
