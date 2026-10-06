"""Unit tests for LLMRouter model routing logic."""

import pytest

from cognitivo.llm_router import LLMRouter, resolve_api_key


@pytest.mark.unit
def test_get_model_config_with_strategy():
    """Retrieves configuration for an active routing strategy."""
    router = LLMRouter()
    config = router.get_model_config("esfuerzo_bajo")
    assert isinstance(config, dict)
    assert "model" in config


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_llm_call():
    """Returns simulated response when mock execution is specified."""
    router = LLMRouter()
    response, model = await router.call_llm("esfuerzo_bajo", "test prompt", mock=True)
    assert isinstance(response, str)
    assert model is not None


@pytest.mark.unit
@pytest.mark.parametrize("reference", ["${OPENROUTER_API_KEY}", "OPENROUTER_API_KEY"])
def test_resolve_api_key_reads_env_references(monkeypatch, reference):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-from-env")

    assert resolve_api_key(reference) == "sk-from-env"


@pytest.mark.unit
@pytest.mark.parametrize("reference", ["${OPENROUTER_API_KEY}", "OPENROUTER_API_KEY"])
def test_resolve_api_key_never_sends_unresolved_references(monkeypatch, reference):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    assert resolve_api_key(reference) is None


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, ""])
def test_resolve_api_key_without_value(value):
    assert resolve_api_key(value) is None
