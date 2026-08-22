from unittest.mock import AsyncMock, patch

import pytest

from memoria.lancedb_manager import LanceDBManager


@pytest.mark.asyncio
async def test_escrutinio_progresivo_exito_inmediato():
    manager = LanceDBManager()

    mock_candidatos = [
        {"text": "Dato altamente relevante", "final_score": 0.85},
        {"text": "Otro dato", "final_score": 0.75}
    ]

    with patch.object(manager, "buscar_hibrido_rrf_impl", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_candidatos

        res = await manager.buscar_con_escrutinio_progresivo(
            query="test query",
            top_k_inicial=3,
            umbral_similitud_inicial=0.7,
            max_intentos=10,
            paso_adaptativo=3
        )

        assert res["status"] == "success"
        assert len(res["results"]) == 2
        assert res["telemetria"]["intentos"] == 1
        assert res["telemetria"]["top_k_final"] == 3
        assert res["telemetria"]["umbral_final"] == 0.7
        assert res["telemetria"]["exito"] is True
        assert mock_search.call_count == 1


@pytest.mark.asyncio
async def test_escrutinio_progresivo_relajacion_adaptativa():
    manager = LanceDBManager()

    # En los primeros 3 intentos el score es 0.66 (por debajo de umbral 0.70)
    # En el intento 4 el umbral baja a 0.65, haciendo match
    candidatos_bajos = [{"text": "Dato con score medio", "final_score": 0.66}]

    with patch.object(manager, "buscar_hibrido_rrf_impl", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = candidatos_bajos

        res = await manager.buscar_con_escrutinio_progresivo(
            query="test adaptativo",
            top_k_inicial=3,
            umbral_similitud_inicial=0.70,
            max_intentos=10,
            paso_adaptativo=3,
            incremento_top_k=2,
            decremento_umbral=0.05
        )

        assert res["status"] == "success"
        assert len(res["results"]) == 1
        # Intento 1..3: umbral 0.70 (sin match). Intento 4: umbral 0.65 (match!)
        assert res["telemetria"]["intentos"] == 4
        assert res["telemetria"]["top_k_final"] == 5
        assert res["telemetria"]["umbral_final"] == 0.65
        assert res["telemetria"]["exito"] is True
        assert mock_search.call_count == 4


@pytest.mark.asyncio
async def test_escrutinio_progresivo_fallback():
    manager = LanceDBManager()

    # Resultados que nunca superan el umbral
    candidatos_irrelevantes = [{"text": "Ruido", "final_score": 0.05}]

    with patch.object(manager, "buscar_hibrido_rrf_impl", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = candidatos_irrelevantes

        res = await manager.buscar_con_escrutinio_progresivo(
            query="query sin resultados",
            top_k_inicial=3,
            umbral_similitud_inicial=0.70,
            max_intentos=10,
            paso_adaptativo=3,
            incremento_top_k=2,
            decremento_umbral=0.05
        )

        assert res["status"] == "fallback"
        assert res["results"] == []
        assert res["telemetria"]["intentos"] == 10
        assert res["telemetria"]["exito"] is False
        assert res["telemetria"]["motivo"] == "Sin coincidencias dentro del margen de confianza"
        assert mock_search.call_count == 10


@pytest.mark.asyncio
async def test_escrutinio_progresivo_consulta_vacia():
    manager = LanceDBManager()

    res = await manager.buscar_con_escrutinio_progresivo(query="")

    assert res["status"] == "fallback"
    assert res["results"] == []
    assert res["telemetria"]["intentos"] == 0
    assert res["telemetria"]["exito"] is False
    assert res["telemetria"]["motivo"] == "Consulta vacía"
