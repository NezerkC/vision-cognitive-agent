"""
Web Search Tool for Visión OS.

Provides a unified web search interface with three backends:
1. DuckDuckGo (primary — free, no API key)
2. Tavily (fallback — requires TAVILY_API_KEY)
3. Mock (last resort — development/testing)

Integrates with LangGraph as a @tool and with the Event Broker as a daemon.
"""

import asyncio
import json
import logging
import os
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Literal

import aiohttp
from ddgs import DDGS  # duckduckgo_search v9+

logger = logging.getLogger("WebSearch")


# ──────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────


@dataclass
class SearchResult:
    """A single search result entry."""

    title: str
    url: str
    snippet: str


@dataclass
class SearchResponse:
    """Standard envelope returned by every search operation."""

    status: Literal["success", "error", "no_results"]
    results: list[SearchResult]
    source: Literal["duckduckgo", "tavily", "mock", "cache"]
    error: str | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class CacheEntry:
    """A cached search result with expiry."""

    results: list[SearchResult]
    source: str
    expires_at: float


# ──────────────────────────────────────────────
# In-Memory Cache
# ──────────────────────────────────────────────


class SearchCache:
    """Simple TTL-based in-memory cache for search results.

    Automatically evicts expired entries and enforces a maximum size.
    """

    def __init__(self, ttl: int = 300, max_size: int = 100):
        """
        Args:
            ttl: Time-to-live in seconds (default: 300 = 5 min).
            max_size: Maximum number of cached entries (default: 100).
        """
        self._cache: dict[str, CacheEntry] = OrderedDict()
        self._ttl = ttl
        self._max_size = max_size

    def _make_key(self, query: str, max_results: int) -> str:
        normalized = " ".join(query.strip().lower().split())
        return f"{normalized}:{max_results}"

    def get(self, query: str, max_results: int) -> SearchResponse | None:
        """Return cached response or None if miss/expired."""
        key = self._make_key(query, max_results)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() < entry.expires_at:
            logger.debug(f"Cache HIT for key: {key}")
            return SearchResponse(
                status="success",
                results=entry.results,
                source="cache",
                timestamp=time.time(),
            )
        # Expired
        del self._cache[key]
        logger.debug(f"Cache EXPIRED for key: {key}")
        return None

    def set(self, query: str, max_results: int, results: list[SearchResult], source: str):
        """Store results in cache."""
        key = self._make_key(query, max_results)
        self._cache[key] = CacheEntry(
            results=results,
            source=source,
            expires_at=time.time() + self._ttl,
        )
        # Enforce max_size
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
        logger.debug(f"Cached {len(results)} results for key: {key} (TTL: {self._ttl}s)")

    @property
    def size(self) -> int:
        return len(self._cache)


# ──────────────────────────────────────────────
# Search Engine
# ──────────────────────────────────────────────


class WebSearchEngine:
    """Unified web search engine with automatic fallback across backends.

    Backend chain: Cache → DuckDuckGo → Tavily → Mock/Error
    """

    def __init__(self, cache_ttl: int = 300):
        self.cache = SearchCache(ttl=cache_ttl)

    async def buscar(self, query: str, max_results: int = 5) -> SearchResponse:
        """
        Execute a web search with automatic fallback.

        Args:
            query: The search query.
            max_results: Maximum number of results (default: 5, max: 10).

        Returns:
            A SearchResponse with results from the first successful backend.
        """
        max_results = min(max_results, 10)  # Hard cap
        if not query or not query.strip():
            return SearchResponse(
                status="error",
                results=[],
                source="mock",
                error="Empty query",
            )

        # 1. Check cache
        cached = self.cache.get(query, max_results)
        if cached:
            return cached

        # 2. Try DuckDuckGo
        try:
            results = await self._search_ddg(query, max_results)
            if results:
                self.cache.set(query, max_results, results, "duckduckgo")
                return SearchResponse(status="success", results=results, source="duckduckgo")
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")

        # 3. Try Tavily fallback
        try:
            results = await self._search_tavily(query, max_results)
            if results:
                self.cache.set(query, max_results, results, "tavily")
                return SearchResponse(status="success", results=results, source="tavily")
        except Exception as e:
            logger.warning(f"Tavily search failed: {e}")

        # 4. All backends failed
        return SearchResponse(
            status="error",
            results=[],
            source="mock",
            error="All search backends failed. Check network or API keys.",
        )

    async def _search_ddg(self, query: str, max_results: int) -> list[SearchResult]:
        """
        Search using DuckDuckGo (sync client wrapped in thread pool).

        DDGS.text() is synchronous; we run it in a thread to avoid blocking.
        """
        loop = asyncio.get_running_loop()

        def _sync_search():
            with DDGS() as ddgs:
                raw = ddgs.text(query, max_results=max_results)
                if not raw:
                    return []
                return [
                    SearchResult(
                        title=r.get("title", ""),
                        url=r.get("href", ""),
                        snippet=r.get("body", ""),
                    )
                    for r in raw
                    if r.get("title") or r.get("body")
                ]

        results = await asyncio.wait_for(
            loop.run_in_executor(None, _sync_search),
            timeout=8.0,
        )
        logger.info(f"DuckDuckGo returned {len(results)} results for '{query}'")
        return results

    async def _search_tavily(self, query: str, max_results: int) -> list[SearchResult]:
        """
        Search using Tavily API via aiohttp.

        Requires TAVILY_API_KEY environment variable.
        """
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY not set in environment")

        async with aiohttp.ClientSession() as session, session.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": False,
                "max_results": max_results,
            },
            timeout=aiohttp.ClientTimeout(total=8),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Tavily returned HTTP {resp.status}")
            data = await resp.json()
            raw_results = data.get("results", [])
            results = [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("content", ""),
                )
                for r in raw_results
            ][:max_results]
            logger.info(f"Tavily returned {len(results)} results for '{query}'")
            return results


# ──────────────────────────────────────────────
# Module-level singleton & LangChain @tool
# ──────────────────────────────────────────────

_engine: WebSearchEngine | None = None


def _get_engine() -> WebSearchEngine:
    global _engine
    if _engine is None:
        _engine = WebSearchEngine()
    return _engine


async def _buscar_en_web_impl(query: str, max_results: int = 5) -> str:
    """Core implementation — used by both the @tool and direct callers."""
    engine = _get_engine()
    response = await engine.buscar(query, max_results)
    return json.dumps(asdict(response), ensure_ascii=False)


# Export the raw function for non-LangChain callers (e.g., graph nodes)
buscar_en_web_func = _buscar_en_web_impl

try:
    from langchain_core.tools import tool

    buscar_en_web = tool(_buscar_en_web_impl)

except ImportError:
    # LangChain not available — use the raw function as fallback
    buscar_en_web = _buscar_en_web_impl
