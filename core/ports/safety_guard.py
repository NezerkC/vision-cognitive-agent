"""
Port specification for Safety and Prompt Injection Guards in Visión OS.
"""

from typing import Protocol


class ISafetyGuard(Protocol):
    """
    Abstract Safety Guard port for perimeter validation and prompt inspection.
    """

    def inspect_prompt(self, prompt: str) -> tuple[bool, str]:
        """
        Inspects prompt for malicious injection or destructive signatures.
        Returns: (is_unsafe, matched_reason)
        """
        ...

    def is_safe_command(self, command: str) -> bool:
        """Verifies if an OS command is permitted to execute."""
        ...
