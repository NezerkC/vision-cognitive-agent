import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sentidos.seguridad_local import accept_local_websocket, install_local_origin_guards, origin_allowed


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "http://127.0.0.1:8000",
        "http://localhost:1420",
        "http://[::1]:8000",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ],
)
def test_origin_allowed_accepts_local_and_originless_clients(origin):
    assert origin_allowed(origin)


@pytest.mark.parametrize(
    "origin",
    ["https://evil.example", "http://127.0.0.1.evil.example", "http://localhost.evil.example:8000", "null"],
)
def test_origin_allowed_rejects_foreign_origins(origin):
    assert not origin_allowed(origin)


@pytest.fixture
def client():
    app = FastAPI()
    install_local_origin_guards(app)

    @app.get("/data")
    async def data():
        return {"ok": True}

    @app.post("/write")
    async def write():
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        if not await accept_local_websocket(websocket):
            return
        await websocket.send_text("hola")
        await websocket.close()

    return TestClient(app)


def test_cross_site_simple_post_is_rejected(client):
    resp = client.post("/write", content="{}", headers={"Origin": "https://evil.example", "Content-Type": "text/plain"})
    assert resp.status_code == 403


def test_local_post_is_allowed(client):
    assert client.post("/write", json={}, headers={"Origin": "http://127.0.0.1:8000"}).status_code == 200


def test_originless_post_is_allowed(client):
    assert client.post("/write", json={}).status_code == 200


def test_cors_does_not_expose_responses_to_foreign_origins(client):
    resp = client.get("/data", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in resp.headers


def test_cors_allows_local_frontend(client):
    resp = client.get("/data", headers={"Origin": "http://localhost:1420"})
    assert resp.headers["access-control-allow-origin"] == "http://localhost:1420"


def test_websocket_from_foreign_origin_is_refused(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws", headers={"Origin": "https://evil.example"}) as ws:
            ws.receive_text()
    assert exc.value.code == 1008


def test_websocket_from_local_origin_is_accepted(client):
    with client.websocket_connect("/ws", headers={"Origin": "http://127.0.0.1:8000"}) as ws:
        assert ws.receive_text() == "hola"
