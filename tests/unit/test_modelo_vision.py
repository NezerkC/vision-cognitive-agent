import json
import sys
from types import SimpleNamespace

import pytest

from cognitivo import llm_router
from cognitivo.llm_router import LLMRouter
from cognitivo.modelo_vision import VisionModelNotConfiguredError, image_message, resolve_vision_model


def _hardware(tmp_path, modelo):
    path = tmp_path / "hardware_interfaces.json"
    path.write_text(json.dumps({"vision_activa": {"modelo_vision": modelo}}), encoding="utf-8")
    return str(path)


def test_local_models_run_on_ollama(tmp_path):
    model = resolve_vision_model(_hardware(tmp_path, "local/qwen3-vl"))

    assert (model.model, model.api_base, model.api_key) == ("ollama/qwen3-vl", "http://localhost:11434", None)


def test_openrouter_models_use_the_openrouter_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    model = resolve_vision_model(_hardware(tmp_path, "openrouter/google/gemini-2.5-flash"))

    assert model.model == "openrouter/google/gemini-2.5-flash"
    assert model.api_base == "https://openrouter.ai/api/v1"
    assert model.api_key == "sk-or-test"


def test_other_litellm_ids_pass_through(tmp_path):
    model = resolve_vision_model(_hardware(tmp_path, "ollama/llava:13b"))

    assert (model.model, model.api_base, model.api_key) == ("ollama/llava:13b", None, None)


@pytest.mark.parametrize("modelo", ["", None])
def test_missing_vision_model_is_an_error(tmp_path, modelo):
    with pytest.raises(VisionModelNotConfiguredError):
        resolve_vision_model(_hardware(tmp_path, modelo))


def test_missing_config_file_is_an_error(tmp_path):
    with pytest.raises(VisionModelNotConfiguredError):
        resolve_vision_model(str(tmp_path / "missing.json"))


def test_image_message_carries_text_and_image():
    message = image_message("¿Qué hay?", "QUJD", mime="image/jpeg")

    assert message == {
        "role": "user",
        "content": [
            {"type": "text", "text": "¿Qué hay?"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}},
        ],
    }


def test_gateway_describes_images_with_the_vision_model(tmp_path):
    import sentidos.sistema_periferico as gateway

    model_name, api_base, _ = gateway.get_vision_model_details(_hardware(tmp_path, "local/qwen3-vl"))

    assert (model_name, api_base) == ("ollama/qwen3-vl", "http://localhost:11434")


class FakeWriter:
    def __init__(self):
        self.events = []

    def write(self, data: bytes):
        self.events.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        pass


@pytest.fixture
def vision_config(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_router, "HARDWARE_CONFIG_PATH", _hardware(tmp_path, "local/qwen3-vl"))


@pytest.fixture
def text_graph_must_not_run(monkeypatch):
    async def graph(*args, **kwargs):
        raise AssertionError("an image request must not go through the text-only graph")

    monkeypatch.setitem(sys.modules, "orquestador_graph", SimpleNamespace(ejecutar_orquestador_graph=graph))


@pytest.mark.asyncio
async def test_image_requests_reach_the_vision_model(monkeypatch, vision_config, text_graph_must_not_run):
    calls = []

    async def completion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Un editor con un error"))])

    monkeypatch.setattr(llm_router.litellm, "acompletion", completion)
    writer = FakeWriter()

    await LLMRouter().process_request(writer, "derecho-1", "¿Qué ves?", "esfuerzo_bajo", image_base64="QUJD")

    assert calls[0]["model"] == "ollama/qwen3-vl"
    assert calls[0]["messages"][0]["content"][1]["image_url"]["url"] == "data:image/jpeg;base64,QUJD"
    response = writer.events[-1]["data"]
    assert response["status"] == "success"
    assert response["response"] == "Un editor con un error"


@pytest.mark.asyncio
async def test_image_requests_fail_when_the_vision_model_fails(monkeypatch, vision_config, text_graph_must_not_run):
    async def unavailable(**kwargs):
        raise ConnectionError("Ollama no responde")

    monkeypatch.setattr(llm_router.litellm, "acompletion", unavailable)
    writer = FakeWriter()

    await LLMRouter().process_request(writer, "derecho-2", "¿Qué ves?", "esfuerzo_bajo", image_base64="QUJD")

    response = writer.events[-1]["data"]
    assert response["status"] == "failed"
    assert "Ollama no responde" in response["error"]
