"""
Domain layer for Visión OS.
Pure domain entities, value objects, and typed event definitions.
"""

from core.domain.emotions import EmotionalState
from core.domain.events import (
    AudioSensorialEventData,
    BaseEventData,
    CognitiveRequestEventData,
    CognitiveResponseEventData,
    EventEnvelope,
    MemoriaEventData,
    SafetyAlertEventData,
    SystemEventData,
    VisionSensorialEventData,
)
from core.domain.memory_entities import Coordinates4D, MemoryRecord, StorageTier

__all__ = [
    "BaseEventData",
    "SystemEventData",
    "MemoriaEventData",
    "VisionSensorialEventData",
    "AudioSensorialEventData",
    "CognitiveRequestEventData",
    "CognitiveResponseEventData",
    "SafetyAlertEventData",
    "EventEnvelope",
    "Coordinates4D",
    "MemoryRecord",
    "StorageTier",
    "EmotionalState",
]
