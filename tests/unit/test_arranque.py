import os

import yaml
from fastapi.testclient import TestClient

from core import arranque

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _write(tmp_path, content: str):
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "arranque.yaml").write_text(content, encoding="utf-8")


def test_missing_key_means_real_mode():
    assert arranque.is_mock({}, "lancedb_manager") is False


def test_explicit_flag_and_global_force_enable_mock():
    assert arranque.is_mock({"lancedb_manager": True}, "lancedb_manager") is True
    assert arranque.is_mock({"lancedb_manager": False}, "lancedb_manager", force=True) is True


def test_load_modos_mock_without_a_config_file_is_empty(tmp_path):
    assert arranque.load_modos_mock(str(tmp_path)) == {}


def test_load_modos_mock_reads_the_config_file(tmp_path):
    _write(tmp_path, "modos_mock:\n  oido_parietal: true\n")

    assert arranque.load_modos_mock(str(tmp_path)) == {"oido_parietal": True}


def test_read_mock_flag_defaults_to_real_mode(tmp_path):
    _write(tmp_path, "modos_mock:\n  oido_parietal: true\n")

    assert arranque.read_mock_flag("oido_parietal", str(tmp_path)) is True
    assert arranque.read_mock_flag("vision_parietal", str(tmp_path)) is False


def test_shipped_config_runs_every_service_for_real():
    with open(os.path.join(ROOT, "config", "arranque.yaml"), encoding="utf-8") as f:
        flags = yaml.safe_load(f)["modos_mock"]

    assert flags and not any(flags.values())


def test_orchestrator_treats_unlisted_services_as_real():
    from core.orchestrator import BrainstemOrchestrator

    orchestrator = BrainstemOrchestrator(enable_tcp_bridge=False)
    orchestrator.modos_mock = {}

    assert orchestrator.is_service_mock("imaginacion_occipital") is False


def test_gateway_default_startup_config_is_real_mode(tmp_path, monkeypatch):
    import sentidos.sistema_periferico as gateway

    monkeypatch.setattr(gateway, "PROJECT_ROOT", str(tmp_path))

    config = TestClient(gateway.app).get("/api/config/arranque").json()["config"]

    assert not any(config["modos_mock"].values())
