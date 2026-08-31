"""
Port specification for Vector Memory Repository in Visión OS.
"""

from typing import Any, Protocol


class IMemoryRepository(Protocol):
    """
    Abstract Vector Memory Repository port.
    """

    async def guardar_memoria(
        self,
        texto: str,
        coordenada_x: float,
        coordenada_y: float,
        coordenada_z: float,
        coordenada_w: float,
        escala_magnitud: str = "KB",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Stores a 4D memory item in vector database."""
        ...

    async def buscar_hibrido_rrf(
        self,
        query: str,
        top_n: int = 5,
        k_rrf: int = 60,
        emotion_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Performs hybrid vector + full-text search with RRF scoring."""
        ...

    async def consolidar_recuerdos(self) -> dict[str, Any]:
        """Consolidates short term memories into cold storage."""
        ...
