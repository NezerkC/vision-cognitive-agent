"""
Port specification for Sensory Perception and Output Actuators in Visión OS.
"""

from typing import Any, Protocol


class ISensoryInput(Protocol):
    """
    Abstract Sensory Perception Port (Vision, Audio, Webhooks).
    """

    async def capture_frame(self) -> dict[str, Any] | None:
        """Captures a single perception unit (e.g. image, audio segment)."""
        ...

    def pause(self) -> None:
        """Pauses background sensory capture."""
        ...

    def resume(self) -> None:
        """Resumes background sensory capture."""
        ...


class ISensoryOutput(Protocol):
    """
    Abstract Actuator Port (Speech, Image Generation, UI Actions).
    """

    async def emit_output(self, payload: dict[str, Any]) -> bool:
        """Emits or executes an output action."""
        ...
