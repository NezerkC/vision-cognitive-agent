"""Contract of the IImageGenerator port shared by the image adapters, the router and the dream cycle."""

import json

import pytest
from pydantic import ValidationError

import core.ports
from core.ports.image_generator import (
    GeneratedImage,
    IImageGenerator,
    ImageGenerationFailedError,
    ImageGeneratorError,
    ImageGeneratorUnavailableError,
    ImageOptions,
)

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


class FakeImageGenerator:
    """Satisfies the port structurally, without inheriting from it."""

    generator_id = "fake"

    async def is_available(self) -> bool:
        return True

    async def generate(self, prompt: str, options: ImageOptions | None = None) -> GeneratedImage:
        applied = (options or ImageOptions()).model_dump(exclude_none=True)
        return GeneratedImage(
            data=PNG, mime_type="image/png", generator_id=self.generator_id, prompt=prompt, metadata=applied
        )


def make_image(**overrides) -> GeneratedImage:
    fields = {"data": PNG, "mime_type": "image/png", "generator_id": "comfyui", "prompt": "un faro", "metadata": {}}
    return GeneratedImage(**(fields | overrides))


def test_a_structural_adapter_satisfies_the_port():
    assert isinstance(FakeImageGenerator(), IImageGenerator)
    assert core.ports.IImageGenerator is IImageGenerator


@pytest.mark.parametrize("missing", ["generator_id", "is_available", "generate"])
def test_an_adapter_missing_a_member_does_not_satisfy_the_port(missing):
    members = {
        name: getattr(FakeImageGenerator, name)
        for name in ("generator_id", "is_available", "generate")
        if name != missing
    }

    assert not isinstance(type("PartialGenerator", (), members)(), IImageGenerator)


@pytest.mark.asyncio
async def test_a_generation_through_the_port_returns_the_image_and_the_options_used():
    generator: IImageGenerator = FakeImageGenerator()

    image = await generator.generate("un faro bajo la lluvia", ImageOptions(width=768, height=512, seed=7))

    assert await generator.is_available()
    assert (image.data, image.mime_type, image.generator_id) == (PNG, "image/png", "fake")
    assert image.metadata == {"width": 768, "height": 512, "seed": 7}


def test_options_default_to_none_so_each_adapter_uses_its_own_defaults():
    assert ImageOptions().model_dump() == {
        "width": None,
        "height": None,
        "seed": None,
        "negative_prompt": None,
        "steps": None,
    }


def test_options_parse_a_request_payload():
    options = ImageOptions.model_validate(
        {"width": 1024, "height": 768, "seed": 0, "negative_prompt": "texto, marcas de agua", "steps": 30}
    )

    assert (options.width, options.height, options.seed, options.steps) == (1024, 768, 0, 30)
    assert options.negative_prompt == "texto, marcas de agua"


@pytest.mark.parametrize(
    "payload",
    [{"width": 0}, {"height": -64}, {"steps": 0}, {"seed": -1}, {"sampler": "euler"}],
    ids=["zero-width", "negative-height", "zero-steps", "negative-seed", "unknown-option"],
)
def test_options_reject_invalid_values_and_unknown_keys(payload):
    with pytest.raises(ValidationError):
        ImageOptions.model_validate(payload)


def test_everything_but_the_bytes_can_be_stored_in_memory_as_json():
    image = make_image(metadata={"seed": 7, "steps": 20, "checkpoint": "sd_xl_base_1.0.safetensors"})

    record = json.loads(json.dumps(image.model_dump(exclude={"data"})))

    assert record == {
        "mime_type": "image/png",
        "generator_id": "comfyui",
        "prompt": "un faro",
        "metadata": {"seed": 7, "steps": 20, "checkpoint": "sd_xl_base_1.0.safetensors"},
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"data": b""},
        {"data": "iVBORw0KGgo="},
        {"mime_type": "text/html"},
        {"generator_id": ""},
        {"prompt": ""},
        {"metadata": {"thumbnail": b"\x89PNG"}},
        {"image_path": "artifacts/faro.png"},
    ],
    ids=[
        "empty-image",
        "base64-text-instead-of-bytes",
        "not-an-image",
        "no-generator",
        "no-prompt",
        "metadata-not-json",
        "unknown-field",
    ],
)
def test_generated_image_rejects_invalid_fields(overrides):
    with pytest.raises(ValidationError):
        make_image(**overrides)


def test_generated_image_is_immutable_and_keeps_its_bytes_out_of_repr():
    image = make_image(data=PNG * 1000)

    with pytest.raises(ValidationError):
        image.prompt = "otra cosa"
    assert repr(image) == "GeneratedImage(mime_type='image/png', generator_id='comfyui', prompt='un faro', metadata={})"


@pytest.mark.parametrize("error_type", [ImageGeneratorUnavailableError, ImageGenerationFailedError])
def test_errors_carry_the_generator_and_the_cause(error_type):
    cause = ConnectionRefusedError("connection refused")

    with pytest.raises(ImageGeneratorError) as raised:
        raise error_type("comfyui", "ComfyUI is unreachable at http://127.0.0.1:8188") from cause

    error = raised.value
    assert type(error) is error_type
    assert error.generator_id == "comfyui"
    assert error.reason == "ComfyUI is unreachable at http://127.0.0.1:8188"
    assert error.__cause__ is cause
    assert str(error) == (
        "comfyui: ComfyUI is unreachable at http://127.0.0.1:8188 (ConnectionRefusedError: connection refused)"
    )


def test_a_cause_without_a_message_is_named_by_its_type():
    with pytest.raises(ImageGenerationFailedError) as raised:
        raise ImageGenerationFailedError("comfyui", "no image after 120 s") from TimeoutError()

    assert str(raised.value) == "comfyui: no image after 120 s (TimeoutError)"


def test_an_error_without_a_cause_reads_as_its_reason():
    error = ImageGeneratorUnavailableError("gemini", "GEMINI_API_KEY is not set")

    assert str(error) == "gemini: GEMINI_API_KEY is not set"
    assert error.__cause__ is None
