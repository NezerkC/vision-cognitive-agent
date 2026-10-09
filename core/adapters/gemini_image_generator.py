"""
Google Gemini API adapter for the IImageGenerator port (cloud option for imagination and dreams).

Flow: client.aio.models.generate_content with response_modalities=["IMAGE"]; the image comes back as an inline
blob in the first candidate's parts. The request is sent with the google-genai SDK.
- No API key configured raises ImageGeneratorUnavailableError from generate() (is_available() returns False).
- Unreachable service, timeouts, a rejected key (HTTP 401/403, or 400 about an invalid API key) and HTTP 503 raise
  ImageGeneratorUnavailableError.
- Other API errors, and a response without an image part, raise ImageGenerationFailedError.
- Never returns a placeholder image.

Options: Gemini does not take seed, negative_prompt, steps or pixel sizes in this call, so those ImageOptions are
not sent and are not recorded in GeneratedImage.metadata. Metadata holds the model only: the response does not
report the image size.

Configuration: config/imaginacion.json, key "gemini" (read by gemini_from_config). The config names the environment
variable that holds the API key (default GEMINI_API_KEY); the key itself is never stored in the repository.
"""

import json
import os
from collections.abc import Mapping
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from core.ports.image_generator import (
    GeneratedImage,
    ImageGenerationFailedError,
    ImageGeneratorUnavailableError,
    ImageOptions,
)

GENERATOR_ID = "gemini"
DEFAULT_MODEL = "gemini-3.1-flash-image"
DEFAULT_API_KEY_ENV = "GEMINI_API_KEY"
DEFAULT_TIMEOUT_SECONDS = 120.0
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "imaginacion.json")

_REJECTED_KEY_CODES = {401, 403}
_UNAVAILABLE_CODES = {503}


def _api_error_to_port(error: genai_errors.APIError) -> Exception:
    code = error.code
    message = error.message or ""
    if code in _REJECTED_KEY_CODES or (code == 400 and "api key" in message.lower()):
        return ImageGeneratorUnavailableError(GENERATOR_ID, f"Gemini API rejected the API key (HTTP {code})")
    if code in _UNAVAILABLE_CODES:
        return ImageGeneratorUnavailableError(GENERATOR_ID, f"Gemini API is unavailable (HTTP {code})")
    return ImageGenerationFailedError(GENERATOR_ID, f"Gemini API error (HTTP {code}): {message or 'no details'}")


def _image_from_response(response: types.GenerateContentResponse) -> tuple[bytes, str]:
    for part in response.parts or []:
        blob = part.inline_data
        if blob is None or not blob.data or not (blob.mime_type or "").startswith("image/"):
            continue
        return blob.data, blob.mime_type
    feedback = getattr(response, "prompt_feedback", None)
    block_reason = getattr(feedback, "block_reason", None)
    detail = f" (prompt blocked: {getattr(block_reason, 'value', block_reason)})" if block_reason else ""
    raise ImageGenerationFailedError(GENERATOR_ID, f"the response contained no image{detail}")


class GeminiImageGenerator:
    """
    IImageGenerator backed by the Gemini API. Pass `client` (an object with an async `aio.models.generate_content`,
    such as genai.Client) to inject a fake in tests; otherwise a client is built from `api_key`.
    Without a client (no key) is_available() is False and generate() raises ImageGeneratorUnavailableError.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        client: Any | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        api_key_env: str = DEFAULT_API_KEY_ENV,
    ):
        self._model = model
        self._api_key_env = api_key_env
        if client is None and api_key and api_key.strip():
            client = genai.Client(
                api_key=api_key.strip(),
                http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
            )
        self._client = client

    @property
    def generator_id(self) -> str:
        return GENERATOR_ID

    async def is_available(self) -> bool:
        return self._client is not None

    async def generate(self, prompt: str, options: ImageOptions | None = None) -> GeneratedImage:
        # `options` is accepted for the port; this API call does not take any of its fields (see module docstring).
        if not prompt or not prompt.strip():
            raise ValueError("prompt must not be empty")
        if self._client is None:
            raise ImageGeneratorUnavailableError(
                GENERATOR_ID,
                f"no API key: set the environment variable named by 'gemini.api_key_env' "
                f"in config/imaginacion.json (currently {self._api_key_env})",
            )

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
        except genai_errors.APIError as e:
            raise _api_error_to_port(e) from e
        except (httpx.TransportError, TimeoutError) as e:
            raise ImageGeneratorUnavailableError(GENERATOR_ID, "Gemini API is unreachable or not answering") from e

        data, mime_type = _image_from_response(response)
        return GeneratedImage(
            data=data,
            mime_type=mime_type,
            generator_id=GENERATOR_ID,
            prompt=prompt,
            metadata={"model": self._model},
        )


def gemini_from_config(
    config_path: str = DEFAULT_CONFIG_PATH,
    environ: Mapping[str, str] | None = None,
) -> GeminiImageGenerator:
    """
    Builds the adapter from the "gemini" entry of config/imaginacion.json. Keys left out keep the defaults.
    The API key is read from the environment variable named by "api_key_env"; a missing or blank value leaves the
    adapter unavailable instead of failing here.
    """
    settings: dict[str, Any] = {}
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            settings = json.load(f).get("gemini") or {}
    env_name = settings.get("api_key_env", DEFAULT_API_KEY_ENV)
    env = os.environ if environ is None else environ
    api_key = (env.get(env_name) or "").strip() or None
    return GeminiImageGenerator(
        api_key=api_key,
        model=settings.get("model", DEFAULT_MODEL),
        timeout_seconds=float(settings.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
        api_key_env=env_name,
    )
