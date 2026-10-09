"""
Port specification for LLM Gateway in Visión OS.
"""

from typing import Any, Protocol


class ILLMGateway(Protocol):
    """
    Abstract LLM Gateway port for dynamic effort-based routing, multimodal inputs, and fallback.
    """

    async def call_model(
        self,
        effort: str,
        prompt: str,
        image_base64: str | None = None,
    ) -> tuple[str, str]:
        """
        Executes a prompt against the configured LLM provider.
        Returns: (response_text, model_name_used)
        """
        ...

    async def generate_json(
        self,
        effort: str,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Generates structured JSON adhering to a specified schema."""
        ...
