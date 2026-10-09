"""Live web search against DuckDuckGo. Needs the network: run with `pytest --run-integration`."""

import pytest

from cognitivo.skills.websearch_tool import WebSearchEngine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_ddg_search():
    results = await WebSearchEngine()._search_ddg("python programming language", 2)

    assert len(results) > 0
    assert results[0].title
    assert results[0].url
