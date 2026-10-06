"""
Pydantic Schemas for Event Broker Communication in Visión OS.
Enforces typed message contracts across microservices and Hexagonal Ports.
"""

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
]
