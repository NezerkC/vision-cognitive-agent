"""
Unit tests for the Gemini image adapter. A fake async client is injected through the constructor, so nothing
reaches the network and no real API key is used.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types

from core.adapters.gemini_image_generator import (
    DEFAULT_API_KEY_ENV,
    DEFAULT_MODEL,
    GeminiImageGenerator,
    gemini_from_config,
)
from core.ports.image_generator import (
    IImageGenerator,
    ImageGenerationFailedError,
    ImageGeneratorUnavailableError,
    ImageOptions,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_CONFIG = PROJECT_ROOT / "config" / "imaginacion.json"
PNG = b"\x89PNG\r\n\x1a\n" + b"image bytes from the fake Gemini client"
TEST_KEY = "test-only-key-not-real"


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, models: FakeModels):
        self.aio = SimpleNamespace(models=models)


def _response(*parts: types.Part) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=list(parts)))])


def _image_response(data: bytes = PNG, mime_type: str = "image/png") -> types.GenerateContentResponse:
    return _response(types.Part(inline_data=types.Blob(data=data, mime_type=mime_type)))


def _generator(models: FakeModels, **kwargs) -> GeminiImageGenerator:
    return GeminiImageGenerator(client=FakeClient(models), api_key=TEST_KEY, **kwargs)


def test_implements_the_port():
    assert isinstance(GeminiImageGenerator(api_key=None), IImageGenerator)
    assert GeminiImageGenerator(api_key=None).generator_id == "gemini"


@pytest.mark.asyncio
async def test_missing_key_is_not_available():
    generator = GeminiImageGenerator(api_key=None)

    assert await generator.is_available() is False


@pytest.mark.asyncio
async def test_missing_key_generate_raises_unavailable_with_reason():
    generator = GeminiImageGenerator(api_key=None)

    with pytest.raises(ImageGeneratorUnavailableError) as info:
        await generator.generate("a lighthouse at dawn")

    assert info.value.generator_id == "gemini"
    assert DEFAULT_API_KEY_ENV in info.value.reason


@pytest.mark.asyncio
async def test_blank_key_from_config_counts_as_missing():
    generator = gemini_from_config(config_path=str(SHIPPED_CONFIG), environ={DEFAULT_API_KEY_ENV: "   "})

    assert await generator.is_available() is False
    with pytest.raises(ImageGeneratorUnavailableError):
        await generator.generate("a lighthouse at dawn")


@pytest.mark.asyncio
async def test_available_with_an_injected_client():
    generator = _generator(FakeModels(response=_image_response()))

    assert await generator.is_available() is True


@pytest.mark.asyncio
async def test_successful_image_maps_bytes_and_metadata():
    models = FakeModels(response=_image_response())
    generator = _generator(models)

    image = await generator.generate("a lighthouse at dawn")

    assert image.data == PNG
    assert image.mime_type == "image/png"
    assert image.generator_id == "gemini"
    assert image.prompt == "a lighthouse at dawn"
    assert image.metadata == {"model": DEFAULT_MODEL}
    call = models.calls[0]
    assert call["model"] == DEFAULT_MODEL
    assert call["contents"] == "a lighthouse at dawn"
    assert call["config"].response_modalities == ["IMAGE"]


@pytest.mark.asyncio
async def test_unsupported_options_are_not_recorded_in_metadata():
    generator = _generator(FakeModels(response=_image_response()))

    image = await generator.generate("a lighthouse", ImageOptions(seed=7, negative_prompt="people", steps=20))

    assert "seed" not in image.metadata
    assert "negative_prompt" not in image.metadata
    assert "steps" not in image.metadata


@pytest.mark.asyncio
async def test_configured_model_is_sent_to_the_api():
    models = FakeModels(response=_image_response())
    generator = _generator(models, model="gemini-2.5-flash-image")

    image = await generator.generate("a lighthouse")

    assert models.calls[0]["model"] == "gemini-2.5-flash-image"
    assert image.metadata == {"model": "gemini-2.5-flash-image"}


@pytest.mark.asyncio
async def test_empty_prompt_is_rejected_before_calling_the_api():
    models = FakeModels(response=_image_response())
    generator = _generator(models)

    with pytest.raises(ValueError):
        await generator.generate("   ")
    assert models.calls == []


@pytest.mark.asyncio
async def test_response_without_an_image_part_raises_failed():
    generator = _generator(FakeModels(response=_response(types.Part(text="I cannot draw that."))))

    with pytest.raises(ImageGenerationFailedError) as info:
        await generator.generate("a lighthouse")

    assert info.value.generator_id == "gemini"
    assert "no image" in info.value.reason


@pytest.mark.asyncio
async def test_response_with_empty_candidates_raises_failed():
    generator = _generator(FakeModels(response=types.GenerateContentResponse(candidates=[])))

    with pytest.raises(ImageGenerationFailedError):
        await generator.generate("a lighthouse")


@pytest.mark.asyncio
async def test_image_part_without_image_mime_type_raises_failed():
    generator = _generator(FakeModels(response=_image_response(mime_type="text/plain")))

    with pytest.raises(ImageGenerationFailedError):
        await generator.generate("a lighthouse")


@pytest.mark.asyncio
async def test_rejected_key_maps_to_unavailable_and_hides_the_key():
    error = genai_errors.ClientError(
        403, {"error": {"code": 403, "message": "Permission denied", "status": "PERMISSION_DENIED"}}
    )
    generator = _generator(FakeModels(error=error))

    with pytest.raises(ImageGeneratorUnavailableError) as info:
        await generator.generate("a lighthouse")

    assert info.value.__cause__ is error
    assert TEST_KEY not in str(info.value)


@pytest.mark.asyncio
async def test_invalid_key_reported_as_bad_request_maps_to_unavailable():
    error = genai_errors.ClientError(
        400,
        {
            "error": {
                "code": 400,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "INVALID_ARGUMENT",
            }
        },
    )
    generator = _generator(FakeModels(error=error))

    with pytest.raises(ImageGeneratorUnavailableError):
        await generator.generate("a lighthouse")


@pytest.mark.asyncio
async def test_other_client_error_maps_to_failed():
    error = genai_errors.ClientError(
        400, {"error": {"code": 400, "message": "Prompt is too long", "status": "INVALID_ARGUMENT"}}
    )
    generator = _generator(FakeModels(error=error))

    with pytest.raises(ImageGenerationFailedError) as info:
        await generator.generate("a lighthouse")

    assert info.value.__cause__ is error


@pytest.mark.asyncio
async def test_server_error_maps_to_failed():
    error = genai_errors.ServerError(500, {"error": {"code": 500, "message": "internal", "status": "INTERNAL"}})
    generator = _generator(FakeModels(error=error))

    with pytest.raises(ImageGenerationFailedError):
        await generator.generate("a lighthouse")


@pytest.mark.asyncio
async def test_unreachable_service_maps_to_unavailable():
    error = httpx.ConnectError("connection refused")
    generator = _generator(FakeModels(error=error))

    with pytest.raises(ImageGeneratorUnavailableError) as info:
        await generator.generate("a lighthouse")

    assert info.value.__cause__ is error


def test_config_reads_the_env_var_name_and_model_not_a_key(tmp_path):
    config = tmp_path / "imaginacion.json"
    config.write_text(
        json.dumps({"gemini": {"api_key_env": "MY_GEMINI", "model": "gemini-2.5-flash-image"}}), encoding="utf-8"
    )

    generator = gemini_from_config(config_path=str(config), environ={"MY_GEMINI": TEST_KEY})

    assert generator._client is not None
    assert generator._model == "gemini-2.5-flash-image"


def test_shipped_config_has_gemini_section_without_a_key_value():
    settings = json.loads(SHIPPED_CONFIG.read_text(encoding="utf-8"))["gemini"]

    assert settings["api_key_env"] == DEFAULT_API_KEY_ENV
    assert settings["model"] == DEFAULT_MODEL
    assert "api_key" not in settings
    assert "key" not in settings
