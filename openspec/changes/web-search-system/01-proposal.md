# SDD Proposal: Web Search System for Visión OS

**Change ID:** `web-search-system`
**Status:** Proposed
**Date:** 2026-07-14
**Author:** SDD Orchestrator

---

## 1. Problem Statement

Visión OS currently lacks a **general-purpose web search capability** that any cognitive module can invoke. The only search that exists is inside `ProtocoloIntriga` (`cognitivo/protocolo_intriga.py`), which exclusively searches Tavily when an on-screen anomaly is detected (error hunting). There is no way for:

- The **LangGraph cognitive graph** to search the web as part of reasoning
- **Skills** (`cognitivo/skills/`) to fetch documentation or troubleshooting info
- **Other daemons** (Amígdala, Ejecutor, etc.) to publish search requests and receive results

## 2. Business Impact

Without web search, Visión OS is blind to the outside world. The system cannot:
- Research solutions to errors it encounters (except via Intriga's narrow path)
- Look up documentation for CLI tools or APIs during autonomous operation
- Provide informed, context-aware responses that require up-to-date information
- Self-train by searching for usage patterns

## 3. Target Users

| User | Use Case |
|------|----------|
| **LangGraph cognitive graph** | Look up facts, docs, and solutions during response synthesis |
| **Protocolo Intriga** | Replace hardcoded Tavily fallback with unified search skill |
| **Auto-capacitación** | Fetch CLI documentation for autonomous tool creation |
| **Any daemon** | Publish `canal.web.busqueda` events and receive structured results |

## 4. Solution Approach

Create a **unified web search module** with three layers:

```
Layer 1: DuckDuckGo (primary) — free, no API key, always available
Layer 2: Tavily (fallback)   — structured results if API key present
Layer 3: Mock (last resort)  — simulated response for development/testing
```

Integrated in two ways:
1. **Standalone skill** → `cognitivo/skills/websearch_tool.py` with a `@tool`-decorated function
2. **Graph node** → `nodo_web` station in `orquestador_graph.py` reachable via `canal.web.busqueda` topic

## 5. Scope

### In Scope

- DuckDuckGo async search via `duckduckgo_search` (already installed)
- Tavily async search as fallback (already implemented in Intriga, will adapt)
- `websearch_tool.py` skill with LangChain `@tool` decorator
- `nodo_web` in the LangGraph StateGraph
- Auto-detection: planificador routes to `nodo_web` when input needs current info
- Event Broker topic: `canal.web.busqueda` for publish/subscribe search requests
- Unified result format: `{ status, results: [{ title, url, snippet }], source: "duckduckgo"|"tavily"|"mock" }`

### Out of Scope

- Web scraping or crawler functionality (this is search only)
- Storing search results long-term (Intriga already saves to LanceDB separately)
- Browser automation (no Playwright/Selenium)
- Image search (text search only)

## 6. Design Constraints

1. **Must be async** — all existing modules use `asyncio`
2. **Must use Event Broker** — communication via TCP pub/sub, not direct calls
3. **Must follow skill pattern** — `@tool` decorator like existing skills
4. **No new dependencies** — `duckduckgo_search` already installed
5. **Graceful degradation** — DDG → Tavily → Mock, never crash

## 7. Risks

| Risk | Mitigation |
|------|------------|
| DuckDuckGo rate limiting | Tavily fallback + exponential backoff in DDG calls |
| No API keys configured | Mock fallback ensures system never blocks |
| Duplicate search routes (Graph vs direct skill) | Graph node delegates to the skill internally |
| Search latency blocks graph execution | Async with timeout (8s default) + non-blocking fire-and-forget for background searches |

## 8. Non-Goals

- This is NOT a replacement for Intriga's anomaly-driven search — Intriga will USE the new module
- This is NOT a web crawler — it searches indexed content
- This is NOT user-facing search — it's an internal system capability

---

## 9. Questions for Next Phase (Spec)

1. Timeout: what's the max acceptable wait for a web search in the graph? (Proposed: 8s)
2. Result count: how many results per search? (Proposed: 5)
3. Should searches be cached in-memory (dict) to avoid repeat queries? (Proposed: yes, TTL 5 min)
