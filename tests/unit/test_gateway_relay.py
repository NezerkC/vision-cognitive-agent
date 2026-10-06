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
