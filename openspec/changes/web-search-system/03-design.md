# SDD Design: Web Search System

**Change ID:** `web-search-system`
**Phase:** Design
**Depends on:** `02-spec.md`
**Date:** 2026-07-14

---

## 1. Architecture Overview

```
                    ┌──────────────────────┐
                    │   Event Broker (TCP)  │
                    │  127.0.0.1:5000       │
                    └──────┬───────────┬────┘
                           │           │
              ┌────────────┴────┐  ┌───┴──────────────┐
              │ canal.web.      │  │ canal.web.        │
              │ busqueda        │  │ resultado         │
              └────────┬───────-┘  └───┬───────────────┘
                       │               │
              ┌────────┴───────────────┴────┐
              │    WebSearchDaemon          │
              │  (cognitivo/web_search.py)  │
              │                             │
              │  ┌─────────────────────┐    │
              │  │  Cache (dict, 5min) │    │
              │  └─────────────────────┘    │
              │  ┌─────────────────────┐    │
              │  │  DuckDuckGo Backend │    │
              │  └─────────────────────┘    │
              │  ┌─────────────────────┐    │
              │  │  Tavily Backend     │    │
              │  └─────────────────────┘    │
              └─────────────────────────────┘

                       │ (imports)
                       ▼
              ┌─────────────────────────────┐
              │  websearch_tool.py          │
              │  @tool buscar_en_web()      │
              └─────────────────────────────┘
                       │ (used by)
              ┌─────────────────────────────┐
              │  orquestador_graph.py       │
              │  nodo_web                   │
              └─────────────────────────────┘
```

## 2. Module: `cognitivo/skills/websearch_tool.py`

### Class: `WebSearchEngine`

```
WebSearchEngine
├── __init__(cache_ttl: int = 300)    # 5 min default TTL
├── _cache: dict[str, CacheEntry]
│
├── buscar(query, max_results=5) -> SearchResult
│   ├── 1. Check _cache → hit? return cached
│   ├── 2. try: _search_ddg(query, max_results)
│   │       → success? cache + return
│   ├── 3. except: try: _search_tavily(query, max_results)
│   │       → success? cache + return
│   ├── 4. except: return error result
│   └── 5. Log every step
│
├── _search_ddg(query, max_results) -> list[Result]
│   └── duckduckgo_search.DDGS().async_text()
│
├── _search_tavily(query, max_results) -> list[Result]
│   └── aiohttp POST → api.tavily.com
│
├── _cache_get(query, max_results) -> list[Result] | None
├── _cache_set(query, max_results, results)
└── _cache_clean()  # evict expired entries every 60s
```

### Data Classes

```python
@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

@dataclass
class SearchResponse:
    status: Literal["success", "error", "no_results"]
    results: list[SearchResult]
    source: Literal["duckduckgo", "tavily", "mock", "cache"]
    error: str | None = None
    timestamp: float = field(default_factory=time.time)

@dataclass
class CacheEntry:
    results: list[SearchResult]
    source: str
    expires_at: float
```

### `@tool` Function

```python
from langchain_core.tools import tool

_engine = WebSearchEngine()

@tool
async def buscar_en_web(query: str, max_results: int = 5) -> str:
    """
    Busca información actual en internet usando DuckDuckGo o Tavily.
    Útil cuando necesitas investigar algo, buscar documentación,
    encontrar soluciones a errores, o consultar noticias recientes.

    Args:
        query: La consulta de búsqueda en lenguaje natural
        max_results: Número máximo de resultados (default: 5, max: 10)

    Returns:
        JSON string con resultados formateados
    """
    response = await _engine.buscar(query, max_results)
    return json.dumps(asdict(response), ensure_ascii=False)
```

## 3. Module: `cognitivo/web_search.py` (Daemon)

### Class: `WebSearchDaemon`

```
WebSearchDaemon
├── __init__(host, port, is_mock)
├── engine: WebSearchEngine          # reuses the skill's engine
│
├── run()                            # main loop → connect to broker
│   ├── subscribe: canal.web.busqueda, system
│   └── event loop → handle events
│
├── handle_search_request(data, writer)
│   ├── extract: request_id, query, max_results, timeout
│   ├── await engine.buscar(query, max_results)
│   └── publish to canal.web.resultado
│
└── run() pattern:
    same as protocolo_intriga.py, ejecutor_izquierdo.py, etc.
```

This daemon is OPTIONAL — the skill alone works when called from the graph.
The daemon exists so non-graph modules can search via the broker.

**Registration in Watchdog** (`core/main.py`):

```python
"web_search": {
    "path": os.path.join(project_root, "cognitivo", "web_search.py"),
    "args": get_args("web_search", "web_search")
}
```

## 4. LangGraph Integration

### `nodo_web` in `orquestador_graph.py`

```python
async def nodo_web(state: EstadoAgente) -> dict:
    logger.info("--- NODO WEB ---")
    input_usuario = state["input_usuario"]
    mock = state.get("mock", False)
    ruta = state.get("ruta_planeada", [])
    nueva_ruta = ruta[1:] if len(ruta) > 0 else []

    if mock:
        return {
            "vagones_informacion": [{
                "estacion": "web",
                "resultado": [{"title": "Mock", "url": "", "snippet": "Simulated web search"}]
            }],
            "ruta_planeada": nueva_ruta
        }

    from skills.websearch_tool import buscar_en_web
    try:
        results_json = await buscar_en_web(query=input_usuario, max_results=5)
        results = json.loads(results_json)
        return {
            "vagones_informacion": [{"estacion": "web", "resultado": results}],
            "ruta_planeada": nueva_ruta
        }
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return {
            "vagones_informacion": [{"estacion": "web", "resultado": {"status": "error", "error": str(e)}}],
            "ruta_planeada": nueva_ruta
        }
```

### Updated Planificador

Add web detection keywords to `nodo_planificador`:

```python
# Web search detection
if any(k in text_lower for k in [
    "buscar", "internet", "web", "google", "investigar",
    "búsqueda", "busqueda", "qué es", "que es",
    "último", "actual", "noticias", "cómo hacer", "como hacer",
    "documentación", "documentacion", "tutorial",
    "última versión", "ultima version"
]):
    ruta.append("web")
```

### Updated Router

Add `"nodo_web"` to the conditional edges in `enrutador_estaciones`:

```python
def enrutador_estaciones(state: EstadoAgente):
    ruta = state.get("ruta_planeada", [])
    if not ruta:
        return "nodo_respuesta"
    next_station = ruta[0]
    if next_station == "memoria":
        return "nodo_memoria"
    elif next_station == "web":
        return "nodo_web"
    elif next_station == "herramientas":
        return "nodo_herramientas"
    else:
        return "nodo_respuesta"
```

### Updated Graph Wiring

```python
workflow.add_node("nodo_web", nodo_web)

workflow.add_conditional_edges(
    "nodo_web",
    enrutador_estaciones,
    {
        "nodo_memoria": "nodo_memoria",
        "nodo_web": "nodo_web",
        "nodo_herramientas": "nodo_herramientas",
        "nodo_respuesta": "nodo_respuesta"
    }
)
```

## 5. DuckDuckGo Backend Detail

Using `duckduckgo_search` async API:

```python
from duckduckgo_search import DDGS

async def _search_ddg(self, query: str, max_results: int) -> list[SearchResult]:
    async with DDGS() as ddgs:
        results = []
        async for result in ddgs.async_text(query, max_results=max_results):
            results.append(SearchResult(
                title=result.get("title", ""),
                url=result.get("href", ""),
                snippet=result.get("body", "")
            ))
        return results
```

**Note**: `DDGS` context manager and `async_text` are the async interfaces. The actual async API may vary by version. Implementation will adapt to what `duckduckgo_search==8.1.1` provides.

## 6. Tavily Backend Detail

Direct HTTP via `aiohttp` (no extra package):

```python
async def _search_tavily(self, query: str, max_results: int) -> list[SearchResult]:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY not set")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "search_depth": "basic", "include_answer": False},
            timeout=aiohttp.ClientTimeout(total=8)
        ) as resp:
            data = await resp.json()
            return [
                SearchResult(title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("content", ""))
                for r in data.get("results", [])
            ][:max_results]
```

## 7. Flow Diagrams

### Graph Flow (web search triggered)

```
User Input → Planificador
                │
                ▼ (detecta keyword "buscar")
           ruta = ["web", "respuesta"]
                │
                ▼
           nodo_memoria (siempre primero)
                │
                ▼
           nodo_web
                │
                ├─ Cache hit? → devuelve cache
                ├─ DDG success? → devuelve resultados
                ├─ Tavily fallback? → devuelve resultados
                └─ All fail? → error resultado
                │
                ▼
           nodo_respuesta (sintetiza con contexto web)
                │
                ▼
           Respuesta Final
```

### Broker Flow (direct daemon search)

```
Daemon X → Event Broker → WebSearchDaemon → Event Broker → Daemon X

Paso 1: Daemon publica en canal.web.busqueda
Paso 2: WebSearchDaemon recibe, ejecuta búsqueda
Paso 3: WebSearchDaemon publica resultado en canal.web.resultado
Paso 4: Daemon X recibe el resultado (estaba suscripto a canal.web.resultado)
```

## 8. Cache Design

```python
import time
from collections import OrderedDict

class SearchCache:
    def __init__(self, ttl: int = 300, max_size: int = 100):
        self._cache: dict[str, CacheEntry] = OrderedDict()
        self._ttl = ttl
        self._max_size = max_size

    def _make_key(self, query: str, max_results: int) -> str:
        return f"{query.strip().lower()}:{max_results}"

    def get(self, query: str, max_results: int) -> SearchResponse | None:
        key = self._make_key(query, max_results)
        entry = self._cache.get(key)
        if entry and time.time() < entry.expires_at:
            return SearchResponse(status="success", results=entry.results,
                                  source="cache", timestamp=time.time())
        if entry:
            del self._cache[key]
        return None

    def set(self, query: str, max_results: int, results: list[SearchResult], source: str):
        key = self._make_key(query, max_results)
        self._cache[key] = CacheEntry(
            results=results,
            source=source,
            expires_at=time.time() + self._ttl
        )
        # Evict oldest if over max_size
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
```

## 9. Configuration

No new config files needed. All configuration is via:
- Environment: `TAVILY_API_KEY` (optional, for Tavily fallback)
- Function params: `max_results`, `cache_ttl`
- Mock mode: `--mock` flag (same as all other daemons)

## 10. Testing Strategy

| Test | What | How |
|------|------|-----|
| Unit: cache | Hit, miss, expiry, max_size eviction | pytest |
| Unit: backends | Mock DDGS + aiohttp responses | pytest + unittest.mock |
| Unit: skill | `buscar_en_web` returns correct format | pytest |
| Integration: graph | `nodo_web` in isolation with mocked engine | pytest-asyncio |
| Integration: broker | Publish to `canal.web.busqueda`, verify response | pytest-asyncio + test broker |

## 11. Migration / Backward Compatibility

- `protocolo_intriga.py` can optionally import `buscar_en_web` instead of calling Tavily directly — this is a non-breaking enhancement, not required for this change
- The existing `call_tavily_search` method in `protocolo_intriga.py` is untouched
- No existing behavior changes
