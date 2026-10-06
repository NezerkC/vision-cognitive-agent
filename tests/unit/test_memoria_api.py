import json
import os

import lancedb
import pyarrow as pa
import pytest
from fastapi.testclient import TestClient

import memoria.cargador_datasets as cargador
import sentidos.sistema_periferico as gateway
from memoria.lancedb_manager import LanceDBManager

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeEmbedder:
    model_id = "fake-embedder"
    dimension = 4

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.0, 0.0]


def _schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            ("vector", pa.list_(pa.float32(), dim)),
            ("text", pa.string()),
            ("coordenada_x", pa.float32()),
            ("coordenada_y", pa.float32()),
            ("coordenada_z", pa.float32()),
            ("coordenada_w", pa.float32()),
            ("escala_magnitud", pa.string()),
            ("metadata", pa.string()),
        ]
    )


@pytest.fixture
def manager(tmp_path):
    mgr = LanceDBManager()
    mgr.db_path = str(tmp_path / "hot")
    mgr.cold_db_path = str(tmp_path / "cold")
    mgr.init_db(embedder=FakeEmbedder())
    return mgr


def test_memory_api_returns_the_stored_nodes(tmp_path, monkeypatch):
    db = lancedb.connect(str(tmp_path / "memoria_activa"))
    db.create_table(
        "memoria_fractal",
        data=[
            {
                "vector": [0.0, 0.0, 0.0, 0.0],
                "text": "Visión aprendió FFmpeg",
                "coordenada_x": 1.5,
                "coordenada_y": -2.0,
                "coordenada_z": 0.5,
                "coordenada_w": 90.0,
                "escala_magnitud": "KB",
                "metadata": json.dumps({"tipo": "solucion_error", "timestamp": 1700000000.0}),
            }
        ],
        schema=_schema(4),
    )
    monkeypatch.setattr(gateway, "PROJECT_ROOT", str(tmp_path))

    nodes = TestClient(gateway.app).get("/api/memoria").json()

    assert nodes == [
        {
            "id": "0",
            "texto": "Visión aprendió FFmpeg",
            "x": 1.5,
            "y": -2.0,
            "z": 0.5,
            "w": 90.0,
            "metadata": {"tipo": "solucion_error", "timestamp": 1700000000.0},
            "timestamp": 1700000000.0,
        }
    ]


@pytest.mark.asyncio
async def test_handle_guardar_reports_whether_it_saved(manager):
    assert await manager.handle_guardar(None, {"text": "hola", "coordenada_w": 90.0}) is True
    assert await manager.handle_guardar(None, {"text": ""}) is False

    manager.table = None
    assert await manager.handle_guardar(None, {"text": "hola", "coordenada_w": 90.0}) is False


@pytest.mark.asyncio
async def test_dataset_loader_writes_the_real_schema_and_tier(manager, monkeypatch):
    monkeypatch.setattr(cargador, "_guardar_manager", manager)

    assert await cargador.guardar_recuerdo("dato frío", temperatura_z=20.0) is True
    assert await cargador.guardar_recuerdo("dato caliente", temperatura_z=90.0) is True

    hot = manager.table.to_arrow().to_pylist()
    cold = manager.cold_table.to_arrow().to_pylist()
    assert [r["text"] for r in hot] == ["dato caliente"]
    assert [r["text"] for r in cold] == ["dato frío"]
    assert cold[0]["coordenada_w"] == 20.0


def test_learning_endpoint_saves_with_the_memory_schema(monkeypatch):
    published = []

    async def record(topic, data):
        published.append((topic, data))
        return True

    monkeypatch.setattr(gateway.gateway, "publish_event", record)

    resp = TestClient(gateway.app).post("/api/memoria/aprender", files={"file": ("nota.txt", b"contenido real")})

    assert resp.status_code == 200
    topic, data = published[0]
    assert topic == "canal.memoria"
    assert "temperatura_z" not in data
    assert data["coordenada_w"] == 100.0


def test_web_hud_has_no_sample_memory_nodes():
    with open(os.path.join(ROOT, "gui", "app.js"), encoding="utf-8") as f:
        source = f.read()

    assert "Opera GX es un navegador gamer" not in source
    assert "placeholderNodes" not in source
