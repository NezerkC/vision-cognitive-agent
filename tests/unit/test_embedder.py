import json

import lancedb
import pyarrow as pa
import pytest

import memoria.lancedb_manager as lm
from memoria.lancedb_manager import (
    BGEM3Embedder,
    EmbedderMismatchError,
    EmbedderUnavailableError,
    check_embedder_compatibility,
    reindex_store,
)


class FakeEmbedder:
    model_id = "fake-embedder"
    dimension = 4

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.0, 0.0]


def test_real_embedder_raises_when_the_model_cannot_load(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("model files not found")

    monkeypatch.setattr(lm.AutoTokenizer, "from_pretrained", unavailable)

    with pytest.raises(EmbedderUnavailableError, match="BAAI/bge-m3"):
        BGEM3Embedder()


def test_real_embedder_raises_instead_of_returning_a_fake_vector(monkeypatch):
    class BrokenModel:
        def to(self, device):
            return self

        def __call__(self, **inputs):
            raise RuntimeError("CUDA out of memory")

    monkeypatch.setattr(lm.AutoTokenizer, "from_pretrained", lambda *a, **k: lambda text, **kw: {})
    monkeypatch.setattr(lm.AutoModel, "from_pretrained", lambda *a, **k: BrokenModel())
    embedder = BGEM3Embedder()

    with pytest.raises(RuntimeError, match="CUDA out of memory"):
        embedder.embed_query("hola")


def test_explicit_mock_embedder_identifies_itself():
    embedder = BGEM3Embedder(force_mock=True)

    assert embedder.model_id == "mock-hash"
    assert embedder.dimension == 1024
    assert embedder.embed_query("hola mundo") == embedder.embed_query("hola mundo")


def test_compatibility_records_the_embedder_of_a_new_store(tmp_path):
    check_embedder_compatibility(str(tmp_path), FakeEmbedder(), has_rows=False)

    assert json.loads((tmp_path / "embedder.json").read_text(encoding="utf-8")) == {
        "model_id": "fake-embedder",
        "dimension": 4,
    }
    check_embedder_compatibility(str(tmp_path), FakeEmbedder(), has_rows=True)


def test_compatibility_rejects_a_different_embedder(tmp_path):
    (tmp_path / "embedder.json").write_text(json.dumps({"model_id": "mock-hash", "dimension": 1024}), encoding="utf-8")

    with pytest.raises(EmbedderMismatchError, match="memoria.reindex"):
        check_embedder_compatibility(str(tmp_path), FakeEmbedder(), has_rows=True)


def test_compatibility_rejects_rows_from_an_unrecorded_embedder(tmp_path):
    with pytest.raises(EmbedderMismatchError, match="memoria.reindex"):
        check_embedder_compatibility(str(tmp_path), FakeEmbedder(), has_rows=True)

    assert not (tmp_path / "embedder.json").exists()


def test_reindex_store_reembeds_every_row_and_records_the_embedder(tmp_path):
    db = lancedb.connect(str(tmp_path))
    schema = pa.schema([("vector", pa.list_(pa.float32(), 4)), ("text", pa.string()), ("extra", pa.string())])
    db.create_table(
        "memoria_fractal",
        data=[
            {"vector": [9.0, 9.0, 9.0, 9.0], "text": "abc", "extra": "x"},
            {"vector": [9.0, 9.0, 9.0, 9.0], "text": "abcdef", "extra": "y"},
        ],
        schema=schema,
    )

    count = reindex_store(str(tmp_path), FakeEmbedder())

    rows = sorted(db.open_table("memoria_fractal").to_arrow().to_pylist(), key=lambda r: r["text"])
    assert count == 2
    assert [r["vector"] for r in rows] == [[3.0, 1.0, 0.0, 0.0], [6.0, 1.0, 0.0, 0.0]]
    assert [r["extra"] for r in rows] == ["x", "y"]
    check_embedder_compatibility(str(tmp_path), FakeEmbedder(), has_rows=True)


def test_reindex_cli_reindexes_the_given_stores(tmp_path, capsys):
    from memoria import reindex

    for name in ("a", "b"):
        db = lancedb.connect(str(tmp_path / name))
        schema = pa.schema([("vector", pa.list_(pa.float32(), 4)), ("text", pa.string())])
        db.create_table("t", data=[{"vector": [0.0, 0.0, 0.0, 0.0], "text": "hola"}], schema=schema)

    exit_code = reindex.main([str(tmp_path / "a"), str(tmp_path / "b")], embedder_factory=FakeEmbedder)

    assert exit_code == 0
    assert "2 rows" in capsys.readouterr().out
    for name in ("a", "b"):
        check_embedder_compatibility(str(tmp_path / name), FakeEmbedder(), has_rows=True)


def test_reindex_cli_defaults_to_the_memory_and_notebook_stores():
    from memoria import reindex

    paths = reindex.default_store_paths()

    assert len(paths) == 3
    assert any(p.endswith("lancedb_cuadernos") for p in paths)


def test_notebook_store_refuses_vectors_from_another_embedder(tmp_path, monkeypatch):
    import cognitivo.cuadernos_manager as cm

    store = tmp_path / "lancedb_cuadernos"
    store.mkdir()
    (store / "embedder.json").write_text(json.dumps({"model_id": "other", "dimension": 1024}), encoding="utf-8")
    monkeypatch.setattr(cm, "LANCE_DB_PATH", str(store))
    monkeypatch.setattr(cm, "BGEM3Embedder", lambda *a, **k: BGEM3Embedder(force_mock=True))

    with pytest.raises(EmbedderMismatchError):
        cm.CuadernosManager()


def test_init_db_refuses_a_store_written_by_another_embedder(tmp_path, monkeypatch):
    (tmp_path / "hot").mkdir()
    (tmp_path / "hot" / "embedder.json").write_text(
        json.dumps({"model_id": "mock-hash", "dimension": 1024}), encoding="utf-8"
    )
    manager = lm.LanceDBManager()
    manager.db_path = str(tmp_path / "hot")
    manager.cold_db_path = str(tmp_path / "cold")

    with pytest.raises(EmbedderMismatchError):
        manager.init_db(embedder=FakeEmbedder())
