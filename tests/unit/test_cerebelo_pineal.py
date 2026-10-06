import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cognitivo.memoria import CerebeloMemoria4D, calcular_distancia_4d
from daemons.pineal_daemon import PinealDaemon


def test_calcular_distancia_4d():
    # 4D metric distance: sqrt(1^2 + 2^2 + 2^2 + 4^2) = sqrt(1+4+4+16) = sqrt(25) = 5.0
    dist = calcular_distancia_4d(1.0, 2.0, 2.0, 4.0)
    assert dist == 5.0


@pytest.mark.asyncio
async def test_cerebelo_memoria_4d():
    cerebelo = CerebeloMemoria4D()
    cerebelo.init_memory(mock_embedder=True)

    # 1. Save memory node
    res = await cerebelo.guardar_recuerdo(
        texto="Test de memoria vectorial 4D para Visión OS",
        coordenada_x=1.0,
        coordenada_y=1.0,
        coordenada_z=1.0,
        coordenada_w=85.0,
    )
    assert res["status"] == "success"
    assert res["tier"] == "hot"

    # 2. Hybrid RRF Search
    search_res = await cerebelo.buscar_hibrida_rrf(query="memoria 4D Visión", top_n=2)
    assert isinstance(search_res, list)
    assert len(search_res) > 0
    assert "text" in search_res[0]
    assert "distancia_4d" in search_res[0]


@pytest.mark.asyncio
async def test_pineal_daemon_consolidation():
    daemon = PinealDaemon(is_mock=True, idle_threshold_seconds=1.0)
    daemon.cerebelo.init_memory(mock_embedder=True)

    # Run sleep cycle routine
    res_cons = await daemon.run_consolidation()
    assert res_cons["status"] == "success"

    summary = await daemon.generate_context_summary()
    assert "Consolidación nocturna" in summary

    triples = await daemon.build_graphrag_index()
    assert isinstance(triples, list)
