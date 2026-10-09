"""Unit tests for the imagination service: it depends only on the IImageGenerator port and publishes every outcome."""

import json
import os

import pytest

from core.ports.image_generator import (
    GeneratedImage,
    ImageGenerationFailedError,
    ImageGeneratorUnavailableError,
)
from sentidos.imaginacion_occipital import ImaginacionOccipital

PNG = b"\x89PNG\r\n\x1a\n" + b"occipital test image"


class FakeWriter:
    def __init__(self):
        self.messages = []

    def write(self, raw: bytes):
        self.messages.append(json.loads(raw.decode("utf-8")))

    async def drain(self):
        pass

    def responses(self):
        return [m["data"] for m in self.messages if m.get("topic") == "canal.imaginacion.respuesta"]


class FakeGenerator:
    generator_id = "comfyui"

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.prompts = []

    async def is_available(self):
        return True

    async def generate(self, prompt, options=None):
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.result


def generated(prompt="un faro") -> GeneratedImage:
    return GeneratedImage(
        data=PNG,
        mime_type="image/png",
        generator_id="comfyui",
        prompt=prompt,
        metadata={"seed": 7, "steps": 20, "prompt_id": "p1"},
    )


async def test_a_generated_image_is_saved_under_artifacts_and_published(tmp_path):
    generator = FakeGenerator(result=generated())
    occipital = ImaginacionOccipital(generator=generator, output_dir=str(tmp_path))
    writer = FakeWriter()

    await occipital.handle_request({"request_id": "req-1", "prompt": "un faro"}, writer)

    [response] = writer.responses()
    assert response["request_id"] == "req-1"
    assert response["status"] == "success"
    assert response["prompt"] == "un faro"
    assert response["generator_id"] == "comfyui"
    assert response["mime_type"] == "image/png"
    assert response["metadata"] == {"seed": 7, "steps": 20, "prompt_id": "p1"}
    assert response["image_url"].startswith("/artifacts/") and response["image_url"].endswith(".png")
    filename = response["image_url"].removeprefix("/artifacts/")
    assert response["image_path"] == os.path.join(str(tmp_path), filename)
    with open(response["image_path"], "rb") as saved:
        assert saved.read() == PNG
    assert generator.prompts == ["un faro"]


@pytest.mark.parametrize(
    "error",
    [
        ImageGeneratorUnavailableError("comfyui", "ComfyUI is unreachable at http://127.0.0.1:8188"),
        ImageGenerationFailedError("comfyui", "node 3 KSampler: CUDA out of memory"),
    ],
)
async def test_a_generator_error_is_published_with_its_reason_and_writes_nothing(tmp_path, error):
    occipital = ImaginacionOccipital(generator=FakeGenerator(error=error), output_dir=str(tmp_path))
    writer = FakeWriter()

    await occipital.handle_request({"request_id": "req-2", "prompt": "un faro"}, writer)

    [response] = writer.responses()
    assert response["status"] == "error"
    assert response["request_id"] == "req-2"
    assert response["prompt"] == "un faro"
    assert response["error"] == str(error)
    assert response.get("image_url") is None
    assert list(tmp_path.iterdir()) == []


async def test_an_unexpected_failure_is_published_as_an_error(tmp_path):
    occipital = ImaginacionOccipital(generator=FakeGenerator(error=RuntimeError("boom")), output_dir=str(tmp_path))
    writer = FakeWriter()

    await occipital.handle_request({"request_id": "req-3", "prompt": "un faro"}, writer)

    [response] = writer.responses()
    assert response["status"] == "error"
    assert "boom" in response["error"]


@pytest.mark.parametrize("event", [{"request_id": "req-4"}, {"request_id": "req-4", "prompt": "   "}])
async def test_a_request_without_a_prompt_gets_an_error_response(tmp_path, event):
    generator = FakeGenerator(result=generated())
    occipital = ImaginacionOccipital(generator=generator, output_dir=str(tmp_path))
    writer = FakeWriter()

    await occipital.handle_request(event, writer)

    [response] = writer.responses()
    assert response["status"] == "error"
    assert response["request_id"] == "req-4"
    assert "prompt" in response["error"]
    assert generator.prompts == []


async def test_mock_mode_generates_nothing_and_says_so(tmp_path):
    generator = FakeGenerator(result=generated())
    occipital = ImaginacionOccipital(generator=generator, output_dir=str(tmp_path), force_mock=True)
    writer = FakeWriter()

    await occipital.handle_request({"request_id": "req-5", "prompt": "un faro"}, writer)

    [response] = writer.responses()
    assert response["status"] == "error"
    assert "mock mode" in response["error"]
    assert generator.prompts == []
    assert list(tmp_path.iterdir()) == []


async def test_without_a_generator_the_request_is_an_error(tmp_path):
    occipital = ImaginacionOccipital(output_dir=str(tmp_path))
    writer = FakeWriter()

    await occipital.handle_request({"request_id": "req-6", "prompt": "un faro"}, writer)

    [response] = writer.responses()
    assert response["status"] == "error"
    assert "No image generator" in response["error"]


def test_the_simulated_image_paths_are_gone():
    assert not hasattr(ImaginacionOccipital, "generate_mock_image")
    assert not hasattr(ImaginacionOccipital, "generate_comfy_image")
