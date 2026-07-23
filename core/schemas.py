"""
Pydantic Schemas for Event Broker Communication in Visión OS.
Enforces typed message contracts across microservices.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class BaseEventData(BaseModel):
    """Base class for all inner event data payloads."""
    model_config = ConfigDict(extra="allow")


class SystemEventData(BaseEventData):
    """System control event data (e.g. purge, shutdown, ping)."""
    action: str = Field(..., description="System action to perform")
    reason: Optional[str] = Field(None, description="Optional explanation or trigger reason")


class MemoriaEventData(BaseEventData):
    """Data payload for memory storage and retrieval operations."""
    action: str = Field(..., description="Memory operation: guardar, buscar, etc.")
    text: Optional[str] = Field(None, description="Text content to process or store")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata key-value pairs")


class VisionSensorialEventData(BaseEventData):
    """Data payload for vision parietal sensory inputs."""
    action: str = Field("analizar_imagen", description="Vision action")
    file_path: str = Field(..., description="Path to image file")
    filename: Optional[str] = Field(None, description="Original filename")
    prompt: Optional[str] = Field(None, description="Custom vision prompt")


class AudioSensorialEventData(BaseEventData):
    """Data payload for audio sensory processing."""
    file_path: str = Field(..., description="Path to raw audio file")
    filename: Optional[str] = Field(None, description="Original filename")


class EventEnvelope(BaseModel):
    """
    Standard message envelope transmitted across TCP Event Broker sockets.
    """
    topic: str = Field(..., description="Target topic name (e.g. canal.memoria)")
    data: Dict[str, Any] = Field(default_factory=dict, description="Inner event payload")

    @classmethod
    def validate_payload(cls, topic: str, data: dict) -> "EventEnvelope":
        """Validate or create an EventEnvelope given topic and data dictionary."""
        return cls(topic=topic, data=data)
