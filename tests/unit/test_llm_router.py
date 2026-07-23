"""Unit tests for LLMRouter model routing logic."""
import pytest

from cognitivo.llm_router import LLMRouter


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
