"""Vision model selection for image analysis (screenshots and uploaded images).

The model comes from `vision_activa.modelo_vision` in config/hardware_interfaces.json and is a LiteLLM model id.
`local/<name>` is shorthand for an Ollama model on this machine; `openrouter/...` ids use OPENROUTER_API_KEY.
"""

import json
import os
from dataclasses import dataclass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARDWARE_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "hardware_interfaces.json")

OLLAMA_API_BASE = "http://localhost:11434"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


class VisionModelNotConfiguredError(RuntimeError):
    """No vision model is configured, so images cannot be analysed."""


@dataclass(frozen=True)
class VisionModel:
    model: str
    api_base: str | None
    api_key: str | None


def resolve_vision_model(config_path: str = HARDWARE_CONFIG_PATH) -> VisionModel:
    try:
        with open(config_path, encoding="utf-8") as f:
            configured = (json.load(f).get("vision_activa") or {}).get("modelo_vision")
    except (OSError, json.JSONDecodeError) as e:
        raise VisionModelNotConfiguredError(f"Could not read the vision model from {config_path}: {e}") from e
    if not configured:
        raise VisionModelNotConfiguredError(
            f"No vision model set: add vision_activa.modelo_vision to {config_path} (for example local/qwen3-vl)."
        )
    if configured.startswith("local/"):
        return VisionModel("ollama/" + configured.removeprefix("local/"), OLLAMA_API_BASE, None)
    if configured.startswith("openrouter/"):
        return VisionModel(configured, OPENROUTER_API_BASE, os.environ.get("OPENROUTER_API_KEY"))
    return VisionModel(configured, None, None)


def image_message(prompt: str, image_base64: str, mime: str = "image/jpeg") -> dict:
    """A user chat message carrying the prompt and the image, in the OpenAI/LiteLLM multimodal format."""
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_base64}"}},
        ],
    }
