"""
Port specification for Image Generation (imagination and dreams) in Visión OS.
"""

import json
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ImageOptions(BaseModel):
    """
    Generation options. None leaves the value to the adapter. Adapters apply the options their backend supports
    and record the values they used in GeneratedImage.metadata.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    width: int | None = Field(None, gt=0, description="Width in pixels")
    height: int | None = Field(None, gt=0, description="Height in pixels")
    seed: int | None = Field(None, ge=0, description="Seed for reproducible images")
    negative_prompt: str | None = Field(None, description="What the image must not show")
    steps: int | None = Field(None, gt=0, description="Sampling steps")


class GeneratedImage(BaseModel):
    """
    One generated image: the encoded bytes plus what memory needs to remember it.
    Saving the bytes to disk is up to the caller.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: bytes = Field(..., min_length=1, strict=True, repr=False, description="Encoded image bytes, not base64")
    mime_type: str = Field(..., pattern=r"^image/[a-z0-9.+-]+$", description="MIME type of data, e.g. image/png")
    generator_id: str = Field(..., min_length=1, description="Id of the generator that produced the image")
    prompt: str = Field(..., min_length=1, description="Prompt the image was generated from")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Parameters actually used (seed, steps, size, model); stored as JSON"
    )

    @field_validator("metadata")
    @classmethod
    def _metadata_is_json(cls, metadata: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(metadata)
        except (TypeError, ValueError) as e:
            raise ValueError(f"metadata is stored in memory as JSON: {e}") from e
        return metadata


class ImageGeneratorError(RuntimeError):
    """
    An image generator could not produce an image. Raise the subclasses with `from cause`:
    the cause stays in __cause__ and is shown in the message.
    """

    def __init__(self, generator_id: str, reason: str):
        super().__init__(generator_id, reason)
        self.generator_id = generator_id
        self.reason = reason

    def __str__(self) -> str:
        message = f"{self.generator_id}: {self.reason}"
        cause = self.__cause__
        if cause is None:
            return message
        detail = f"{type(cause).__name__}: {cause}" if str(cause) else type(cause).__name__
        return f"{message} ({detail})"


class ImageGeneratorUnavailableError(ImageGeneratorError):
    """The generator cannot be used now (service unreachable, API key missing); routing may try the next one."""


class ImageGenerationFailedError(ImageGeneratorError):
    """The generator was reached but produced no image (rejected prompt, workflow error, timeout, empty output)."""


@runtime_checkable
class IImageGenerator(Protocol):
    """
    Abstract Image Generator port (local ComfyUI, cloud Gemini) for imagination requests and dreams.
    Adapters never return placeholder images: when they cannot produce a real one they raise.
    """

    @property
    def generator_id(self) -> str:
        """Stable id of the generator (e.g. 'comfyui'), used in results, errors and logs."""
        ...

    async def is_available(self) -> bool:
        """
        Cheap check, without generating, that the backend can be used now (service reachable, API key set).
        Returns False instead of raising when it cannot.
        """
        ...

    async def generate(self, prompt: str, options: ImageOptions | None = None) -> GeneratedImage:
        """
        Generates one image for the prompt.
        Raises ImageGeneratorUnavailableError when the backend cannot be used
        and ImageGenerationFailedError when it produced no image.
        """
        ...
