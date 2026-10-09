"""The gateway relays uploads, external webhooks and the HUD panic button to the event broker."""

import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import sentidos.sistema_periferico as gateway


class Published(list):
    """(topic, data) pairs the gateway published. WebSocket handlers run on the TestClient's portal thread."""

    def __init__(self):
        super().__init__()
        self.arrived = threading.Event()

    async def record(self, topic: str, data: dict) -> bool:
        self.append((topic, data))
        self.arrived.set()
        return True


@pytest.fixture
def published(monkeypatch):
    recorder = Published()
    monkeypatch.setattr(gateway.gateway, "publish_event", recorder.record)
    return recorder


def test_upload_sensorial_saves_the_file_and_announces_it(published, monkeypatch, tmp_path):
    monkeypatch.setattr(gateway, "TEMP_UPLOAD_DIR", str(tmp_path))

    resp = TestClient(gateway.app).post("/upload_sensorial", files={"file": ("notas.txt", b"contenido sensorial")})

    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    saved = tmp_path / "notas.txt"
    assert saved.read_bytes() == b"contenido sensorial"
    [(topic, data)] = published
    assert topic == "canal.sensorial.archivo_recibido"
    assert data["nombre"] == "notas.txt"
    assert Path(data["ruta_local"]) == saved


def test_websocket_panic_purges_the_broker_queues(published):
    with TestClient(gateway.app).websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"action": "panic"}))
        # Leaving the session cancels the handler, so wait until it has published.
        assert published.arrived.wait(timeout=5)

    [(topic, data)] = published
    assert topic == "system"
    assert data["action"] == "purge"


def test_external_webhook_is_relayed_to_the_broker(published):
    payload = {"event": "git_push", "repo": "vision-os", "author": "NezerkC"}

    resp = TestClient(gateway.app).post("/webhook/externo", json=payload)

    assert resp.status_code == 200
    assert resp.json()["status"] == "forwarded"
    assert published == [("canal.sensorial.periferico", payload)]


def test_pc_action_request_is_queued_for_human_approval(published):
    resp = TestClient(gateway.app).post(
        "/api/ejecucion/accion", json={"herramienta": "ejecutar_script", "parametros": ["dir"]}
    )

    assert resp.status_code == 202
    request_id = resp.json()["request_id"]
    assert request_id.startswith("accion-")
    [(topic, data)] = published
    assert topic == "canal.ejecucion.accion"
    assert data["request_id"] == request_id
    assert data["herramienta"] == "ejecutar_script"
    assert data["parametros"] == ["dir"]


@pytest.mark.parametrize(
    "body",
    [
        {"herramienta": "borrar_todo", "parametros": ["rm -rf /"]},
        {"herramienta": "ejecutar_script"},
        {"herramienta": "ejecutar_script", "parametros": []},
        {"herramienta": "control_ui", "parametros": [1]},
    ],
)
def test_invalid_pc_action_is_rejected_without_reaching_the_broker(published, body):
    resp = TestClient(gateway.app).post("/api/ejecucion/accion", json=body)

    assert resp.status_code == 400
    assert published == []


def test_pc_action_reports_an_offline_broker_instead_of_pretending_it_was_queued(monkeypatch):
    async def offline(topic, data):
        return False

    monkeypatch.setattr(gateway.gateway, "publish_event", offline)

    resp = TestClient(gateway.app).post(
        "/api/ejecucion/accion", json={"herramienta": "control_ui", "parametros": ["win"]}
    )

    assert resp.status_code == 503
    assert resp.json()["status"] == "error"
