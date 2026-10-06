import json
import time

import pytest
from fastapi.testclient import TestClient

import core.orchestrator as orchestrator_module
import sentidos.sistema_periferico as gateway
from cognitivo.memoria import CerebeloMemoria4D
from core.orchestrator import BrainstemOrchestrator


@pytest.mark.asyncio
async def test_failed_memory_save_is_reported(monkeypatch):
    cerebelo = CerebeloMemoria4D()

    async def not_saved(writer, data):
        return False

    monkeypatch.setattr(cerebelo.db_manager, "handle_guardar", not_saved)

    result = await cerebelo.guardar_recuerdo(texto="hola")

    assert result["status"] == "error"


@pytest.fixture
def orchestrator(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "RESTART_DELAY_SECONDS", 0)
    return BrainstemOrchestrator(enable_tcp_bridge=False)


@pytest.mark.asyncio
async def test_supervisor_records_crashes_and_restarts(orchestrator):
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("se cayó el servicio")
        orchestrator.should_run = False

    await orchestrator._supervise("Servicio", flaky)

    status = orchestrator.service_status["Servicio"]
    assert status["restarts"] == 1
    assert "se cayó el servicio" in status["last_error"]


@pytest.mark.asyncio
async def test_health_snapshot_reports_running_services(orchestrator):
    snapshots = []

    async def runs_once():
        orchestrator.should_run = False
        snapshots.append(orchestrator.health_snapshot())

    await orchestrator._supervise("Servicio", runs_once)

    service = snapshots[0]["services"]["Servicio"]
    assert service["status"] == "running"
    assert isinstance(service["uptime_s"], int)


def test_orchestrator_writes_the_health_file_the_gateway_reads(orchestrator, tmp_path):
    orchestrator.project_root = str(tmp_path)
    orchestrator.service_status["Servicio"] = {"status": "running", "started_at": time.time(), "restarts": 0}

    orchestrator.write_health_file()

    data = json.loads((tmp_path / "config" / ".health_status.json").read_text(encoding="utf-8"))
    assert data["services"]["Servicio"]["status"] == "running"
    assert time.time() - data["timestamp"] < 5


@pytest.mark.parametrize("age, stale", [(0, False), (60, True)])
def test_health_endpoint_flags_stale_status(tmp_path, monkeypatch, age, stale):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / ".health_status.json").write_text(
        json.dumps({"services": {"Servicio": {"status": "running"}}, "timestamp": time.time() - age}),
        encoding="utf-8",
    )
    monkeypatch.setattr(gateway, "PROJECT_ROOT", str(tmp_path))

    health = TestClient(gateway.app).get("/api/health").json()

    assert health["services"]["Servicio"]["status"] == "running"
    assert health["stale"] is stale


def test_health_endpoint_without_status_file_is_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway, "PROJECT_ROOT", str(tmp_path))

    health = TestClient(gateway.app).get("/api/health").json()

    assert health["services"] == {}
    assert health["stale"] is True
