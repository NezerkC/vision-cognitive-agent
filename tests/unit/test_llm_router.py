"""Unit tests for LLMRouter model routing logic."""

import inspect
import json
import sys
from types import SimpleNamespace

import pytest

from cognitivo import llm_router
from cognitivo.llm_router import LLMRouter, resolve_api_key


@pytest.mark.unit
def test_get_model_config_with_strategy():
    """Retrieves configuration for an active routing strategy."""
    router = LLMRouter()
    config = router.get_model_config("esfuerzo_bajo")
    assert isinstance(config, dict)
    assert "model" in config


class _FakeChoice:
    def __init__(self, content):
        self.message = type("Message", (), {"content": content})()


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class FakeWriter:
    def __init__(self):
        self.events = []

    def write(self, data: bytes):
        self.events.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        pass


@pytest.fixture
def no_model_pull(monkeypatch):
    async def present(*args, **kwargs):
        return True

    monkeypatch.setattr(llm_router, "pull_model_if_missing", present)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.mark.unit
def test_call_llm_has_no_mock_mode():
    assert "mock" not in inspect.signature(LLMRouter.call_llm).parameters
    assert "mock" not in inspect.signature(llm_router.enrutar_peticion).parameters


@pytest.mark.unit
@pytest.mark.asyncio
async def test_call_llm_returns_the_model_answer(monkeypatch, no_model_pull):
    async def completion(**kwargs):
        return _FakeCompletion("respuesta real")

    monkeypatch.setattr(llm_router.litellm, "acompletion", completion)

    response, model = await LLMRouter().call_llm("esfuerzo_bajo", "test prompt")

    assert response == "respuesta real"
    assert model


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("estado", "temperature"), [("neutral", 0.3), ("lógico", 0.0), ("creativo", 0.8), ("intriga", 0.8)]
)
async def test_call_llm_emotion_overrides_the_effort_temperature(
    monkeypatch, tmp_path, no_model_pull, estado, temperature
):
    effort_levels = tmp_path / "effort_levels.json"
    effort_levels.write_text(json.dumps({"esfuerzo_bajo": {"temperature": 0.3, "max_tokens": 256}}), encoding="utf-8")
    emotions = tmp_path / "emotions.json"
    emotions.write_text(json.dumps({"estado": estado, "intensidad": 0.9}), encoding="utf-8")
    monkeypatch.setattr(llm_router, "EFFORT_LEVELS_PATH", str(effort_levels))
    monkeypatch.setattr(llm_router, "EMOTIONS_PATH", str(emotions))
    calls = []

    async def completion(**kwargs):
        calls.append(kwargs)
        return _FakeCompletion("4")

    monkeypatch.setattr(llm_router.litellm, "acompletion", completion)

    await LLMRouter().call_llm("esfuerzo_bajo", "¿Cuánto es 2+2?")

    [call] = calls
    assert call["temperature"] == temperature


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrutar_peticion_raises_when_every_model_fails(monkeypatch, no_model_pull):
    async def unavailable(**kwargs):
        raise ConnectionError("no model reachable")

    monkeypatch.setattr(llm_router.litellm, "acompletion", unavailable)
    monkeypatch.setattr(llm_router, "_global_router", None)

    with pytest.raises(ConnectionError):
        await llm_router.enrutar_peticion("hola")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_request_publishes_failed_when_the_graph_raises(monkeypatch):
    async def broken_graph(*args, **kwargs):
        raise RuntimeError("LLM caído")

    monkeypatch.setitem(sys.modules, "orquestador_graph", SimpleNamespace(ejecutar_orquestador_graph=broken_graph))
    writer = FakeWriter()

    await LLMRouter().process_request(writer, "req-9", "hola", "esfuerzo_bajo")

    response = writer.events[-1]["data"]
    assert response["status"] == "failed"
    assert response["request_id"] == "req-9"
    assert "LLM caído" in response["error"]
    assert "response" not in response


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_request_publishes_the_graph_answer(monkeypatch):
    async def graph(prompt, request_id, memory_search=None):
        return f"respuesta a {prompt}"

    monkeypatch.setitem(sys.modules, "orquestador_graph", SimpleNamespace(ejecutar_orquestador_graph=graph))
    writer = FakeWriter()

    await LLMRouter().process_request(writer, "req-10", "hola", "esfuerzo_bajo")

    response = writer.events[-1]["data"]
    assert response["status"] == "success"
    assert response["response"] == "respuesta a hola"


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
