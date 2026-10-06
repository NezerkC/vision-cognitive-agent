"""
Cerebellum 4D Vector Memory Module for Visión OS.

Implements the CerebeloMemoria4D engine using a 4D spatial metric:
    D² = X² + Y² + Z² + W²
where W represents emotional gravity / intrigue weight. High W values
reduce quadratic distance, effectively pulling heavy memories from the cold
tier into the hot tier.
"""

import asyncio
import logging
import math
import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memoria.lancedb_manager import LanceDBManager

logger = logging.getLogger("CerebeloMemoria4D")


def calcular_distancia_4d(
    x1: float, y1: float, z1: float, w1: float, x2: float = 0.0, y2: float = 0.0, z2: float = 0.0, w2: float = 0.0
) -> float:
    """
    Computes the 4D spatial quadratic distance metric:
        D² = (X1 - X2)² + (Y1 - Y2)² + (Z1 - Z2)² + (W1 - W2)²
    """
    dx = x1 - x2
    dy = y1 - y2
    dz = z1 - z2
    dw = w1 - w2
    return math.sqrt(dx * dx + dy * dy + dz * dz + dw * dw)


class CerebeloMemoria4D:
    """
    Cerebellum memory manager operating dual Hot/Cold storage tiering:
    - Hot Zone (SSD/RAM - HNSW index): Recent memories & high W (emotion/intrigue) factor.
    - Cold Zone (HDD/Archive - PQ index): Compressed long-term historical records.
    """

    def __init__(self, db_manager: LanceDBManager | None = None):
        self.db_manager = db_manager or LanceDBManager()
        self.hot_w_threshold = 70.0  # Memories with W >= 70 stay in Hot Tier

    def init_memory(self, mock_embedder: bool = False):
        """Initializes the underlying LanceDB tables and indexes."""
        self.db_manager.init_db(mock_embedder=mock_embedder)

    def route_tier(self, coordenada_w: float) -> str:
        """Determines whether a memory node belongs in the Hot or Cold tier based on W factor."""
        if coordenada_w >= self.hot_w_threshold:
            return "hot"
        return "cold"

    async def guardar_recuerdo(
        self,
        texto: str,
        coordenada_x: float = 0.0,
        coordenada_y: float = 0.0,
        coordenada_z: float = 0.0,
        coordenada_w: float = 100.0,
        escala_magnitud: str = "KB",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Stores a new 4D memory entry into LanceDB, routing to Hot/Cold storage
        based on emotional/intrigue weight (W).
        """
        tier = self.route_tier(coordenada_w)
        meta = metadata or {}
        meta["tier"] = tier

        payload = {
            "text": texto,
            "coordenada_x": float(coordenada_x),
            "coordenada_y": float(coordenada_y),
            "coordenada_z": float(coordenada_z),
            "coordenada_w": float(coordenada_w),
            "escala_magnitud": escala_magnitud,
            "metadata": meta,
        }

        # Delegate execution to database manager
        await self.db_manager.handle_guardar(writer=None, data=payload)

        dist_origen = calcular_distancia_4d(coordenada_x, coordenada_y, coordenada_z, coordenada_w)
        return {
            "status": "success",
            "tier": tier,
            "distancia_4d_origen": dist_origen,
            "text": texto,
        }

    async def buscar_hibrida_rrf(
        self,
        query: str,
        top_n: int = 5,
        k_rrf: int = 60,
        emotion_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Executes a 4D Hybrid RRF (Reciprocal Rank Fusion) search across LanceDB memory tables.
        RRF combines dense vector similarity ranking and Tantivy FTS keyword search:
            RRF_Score(d) = 1/(k + Rank_vec) + 1/(k + Rank_fts)
        Final scores are weighted by 4D distance D² = X² + Y² + Z² + W².
        """
        return await self.db_manager.buscar_hibrido_rrf_impl(
            query=query,
            top_n=top_n,
            k_rrf=k_rrf,
            emotion_filter=emotion_filter,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cerebelo = CerebeloMemoria4D()
    cerebelo.init_memory(mock_embedder=True)

    async def test():
        res = await cerebelo.guardar_recuerdo("Prueba de memoria 4D", 1.0, 2.0, 3.0, 85.0)
        print("Guardar:", res)
        results = await cerebelo.buscar_hibrida_rrf("Prueba memoria", top_n=3)
        print("Resultados RRF:", results)

    asyncio.run(test())
