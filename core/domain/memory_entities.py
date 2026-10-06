"""
Domain entities and value objects for 4D Memory in Visión OS.
"""

import math
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StorageTier(StrEnum):
    """Storage tiers in hot/cold memory architecture."""

    HOT = "hot"  # SSD / RAM (Active fast retrieval)
    WARM = "warm"  # SSD / Compressed (Weekly context)
    COLD = "cold"  # HDD (Long term archive)
    FROZEN = "frozen"  # Deep Compressed / Synthesized


class Coordinates4D(BaseModel):
    """4D spatial representation of memories in fractal base-3 coordinate space."""

    x: float = Field(0.0, description="Semantic cosine coordinate X")
    y: float = Field(0.0, description="Semantic cosine coordinate Y")
    z: float = Field(100.0, description="Temperature / recency coordinate Z (0=cold, 100=hot)")
    w: float = Field(0.0, description="Emotional gravity / intrigue weight W")
    magnitude: str = Field("KB", description="Scale magnitude (KB=mm, MB=cm, GB=m, TB=km)")

    def distance_to(self, other: "Coordinates4D") -> float:
        """Calculates 4D quadratic Euclidean distance."""
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        dw = self.w - other.w
        return math.sqrt(dx * dx + dy * dy + dz * dz + dw * dw)


class MemoryRecord(BaseModel):
    """Immutable domain representation of a consolidated memory item."""

    id: str = Field(..., description="Unique memory chunk identifier")
    text: str = Field(..., description="Indexed textual content")
    coordinates: Coordinates4D = Field(default_factory=Coordinates4D)
    tier: StorageTier = Field(default=StorageTier.HOT)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
