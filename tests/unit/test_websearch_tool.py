"""Tests for the web search tool. Backends are patched: these tests never touch the network.

The live DuckDuckGo check is in tests/integration/test_websearch_live.py.
"""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from cognitivo.skills import websearch_tool
from cognitivo.skills.websearch_tool import (
    SearchCache,
    SearchResult,
    WebSearchEngine,
    buscar_en_web_func,
)


def _results(source: str, count: int) -> list[SearchResult]:
    """`count` results with URLs unique to `source`."""
    return [
        SearchResult(title=f"{source} {i}", url=f"https://example.com/{source}/{i}", snippet="") for i in range(count)
    ]


# ──────────────────────────────────────────────
# SearchCache Tests
# ──────────────────────────────────────────────


class TestSearchCache:
    def test_cache_miss(self):
        cache = SearchCache(ttl=60)
        result = cache.get("python", 5)
        assert result is None

    def test_cache_hit(self):
        cache = SearchCache(ttl=60)
        results = [SearchResult(title="Test", url="https://x.com", snippet="test snippet")]
        cache.set("python", 5, results, "duckduckgo")

        hit = cache.get("python", 5)
        assert hit is not None
        assert hit.status == "success"
        assert hit.source == "cache"
        assert len(hit.results) == 1
        assert hit.results[0].title == "Test"

    def test_cache_expiry(self):
        cache = SearchCache(ttl=0)  # Instant expiry
        results = [SearchResult(title="Test", url="https://x.com", snippet="test")]
        cache.set("python", 5, results, "duckduckgo")
        time.sleep(0.01)
        hit = cache.get("python", 5)
        assert hit is None

    def test_cache_max_size(self):
        cache = SearchCache(ttl=60, max_size=3)
        for i in range(5):
            q = f"query-{i}"
            results = [SearchResult(title=f"R{i}", url="", snippet="")]
            cache.set(q, 3, results, "duckduckgo")

        # Only the last 3 entries should survive
        assert cache.size == 3
        assert cache.get("query-0", 3) is None  # evicted
        assert cache.get("query-4", 3) is not None  # newest

    def test_cache_normalized_key(self):
        cache = SearchCache(ttl=60)
        results = [SearchResult(title="Test", url="", snippet="")]
        cache.set("  Hello World  ", 5, results, "ddg")

        hit = cache.get("hello world", 5)
        assert hit is not None

    def test_cache_different_max_results(self):
        cache = SearchCache(ttl=60)
        r5 = [SearchResult(title="R5", url="", snippet="")]
        cache.set("python", 5, r5, "ddg")

        r10 = [SearchResult(title="R10", url="", snippet="")]
        cache.set("python", 10, r10, "ddg")

        assert len(cache._cache) == 2
        assert cache.get("python", 5).results[0].title == "R5"
        assert cache.get("python", 10).results[0].title == "R10"


# ──────────────────────────────────────────────
# WebSearchEngine Tests
# ──────────────────────────────────────────────


class TestWebSearchEngine:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query", ["", "   "])
    async def test_empty_query(self, query):
        result = await WebSearchEngine().buscar(query, 5)

        assert result.status == "error"
        assert result.source == "none"
        assert result.results == []

    @pytest.mark.asyncio
    async def test_max_results_capped(self):
        """More than 10 results takes the deep-search path, which returns at most 50."""
        engine = WebSearchEngine()

        async def ddg(query, max_results):
            return _results(query, max_results)

        with (
            patch.object(engine, "_search_ddg", AsyncMock(side_effect=ddg)) as mock_ddg,
            patch.object(engine, "_search_tavily", AsyncMock(return_value=_results("tavily", 60))) as mock_tavily,
        ):
            result = await engine.buscar("python", 100)

        assert result.status == "success"
        assert len(result.results) == 50
        assert mock_ddg.call_count == 4  # one call per deep-search sub-query
        mock_tavily.assert_called_once_with("python", max_results=50)

    @pytest.mark.asyncio
    async def test_deep_search_without_results_is_an_error(self):
        engine = WebSearchEngine()
        with (
            patch.object(engine, "_search_ddg", AsyncMock(return_value=[])),
            patch.object(engine, "_search_tavily", AsyncMock(side_effect=ValueError("TAVILY_API_KEY not set"))),
        ):
            result = await engine.buscar("python", 25)

        assert result.status == "error"
        assert result.source == "none"
        assert result.results == []

    @pytest.mark.asyncio
    async def test_ddg_fallback_to_error(self):
        """If every backend fails, the search returns an error with no results."""
        engine = WebSearchEngine()
        with (
            patch.object(engine, "_search_ddg", AsyncMock(side_effect=Exception("DDG down"))),
            patch.object(engine, "_search_tavily", AsyncMock(side_effect=ValueError("TAVILY_API_KEY not set"))),
        ):
            result = await engine.buscar("python test", 3)

        assert result.status == "error"
        assert result.source == "none"
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_tavily_called_when_ddg_fails(self):
        """If DDG returns empty, should try Tavily."""
        engine = WebSearchEngine()
        tavily_results = [SearchResult(title="Tavily Result", url="https://tavily.com", snippet="From Tavily")]

        with (
            patch.object(engine, "_search_ddg", AsyncMock(return_value=[])),
            patch.object(engine, "_search_tavily", AsyncMock(return_value=tavily_results)),
        ):
            result = await engine.buscar("python", 3)
            assert result.status == "success"
            assert result.source == "tavily"
            assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_cache_used_on_second_call(self):
        """First call hits DDG, second call hits cache."""
        engine = WebSearchEngine()
        ddg_results = [SearchResult(title="DDG Result", url="https://ddg.com", snippet="From DDG")]

        with patch.object(engine, "_search_ddg", AsyncMock(return_value=ddg_results)) as mock_ddg:
            # First call
            result1 = await engine.buscar("test caching", 3)
            assert result1.source == "duckduckgo"
            assert mock_ddg.call_count == 1

            # Second call — should use cache
            result2 = await engine.buscar("test caching", 3)
            assert result2.source == "cache"
            assert mock_ddg.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_ddg_success_returns_immediately(self):
        """If DDG returns results, don't call Tavily."""
        engine = WebSearchEngine()
        ddg_results = [SearchResult(title="DDG", url="https://ddg.com", snippet="")]

        with (
            patch.object(engine, "_search_ddg", AsyncMock(return_value=ddg_results)) as mock_ddg,
            patch.object(engine, "_search_tavily", AsyncMock()) as mock_tavily,
        ):
            result = await engine.buscar("python", 3)
            assert result.source == "duckduckgo"
            mock_ddg.assert_called_once()
            mock_tavily.assert_not_called()


# ──────────────────────────────────────────────
# buscar_en_web_func Tests
# ──────────────────────────────────────────────


class TestBuscarEnWeb:
    @pytest.mark.asyncio
    async def test_returns_valid_json(self, monkeypatch):
        """The function returns the module engine's response as a JSON string."""
        engine = WebSearchEngine()
        ddg_results = [SearchResult(title="DDG", url="https://ddg.com", snippet="From DDG")]
        monkeypatch.setattr(engine, "_search_ddg", AsyncMock(return_value=ddg_results))
        monkeypatch.setattr(websearch_tool, "_engine", engine)

        result = await buscar_en_web_func("test query", 1)

        assert isinstance(result, str)
        data = json.loads(result)
        assert data["status"] == "success"
        assert data["source"] == "duckduckgo"
        assert data["results"] == [{"title": "DDG", "url": "https://ddg.com", "snippet": "From DDG"}]
        assert "timestamp" in data
