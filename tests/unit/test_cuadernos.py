import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import cognitivo.cuadernos_manager as cm
from cognitivo.cuadernos_manager import CuadernosManager
from memoria.lancedb_manager import BGEM3Embedder


@pytest.fixture
def cuadernos_mgr(monkeypatch, tmp_path):
    monkeypatch.setattr("cognitivo.cuadernos_manager.CUADERNOS_DIR", str(tmp_path))
    monkeypatch.setattr("cognitivo.cuadernos_manager.METADATA_FILE", str(tmp_path / "notebooks.json"))
    monkeypatch.setattr("cognitivo.cuadernos_manager.SOURCES_DIR", str(tmp_path / "sources"))
    monkeypatch.setattr("cognitivo.cuadernos_manager.LANCE_DB_PATH", str(tmp_path / "lancedb_cuadernos"))
    # Deterministic offline embeddings: unit tests must not load the multi-GB BGE-M3 model.
    monkeypatch.setattr(
        "cognitivo.cuadernos_manager.BGEM3Embedder", lambda *args, **kwargs: BGEM3Embedder(force_mock=True)
    )

    return CuadernosManager()


@pytest.fixture
def fake_web_search(monkeypatch):
    """Offline WebSearchEngine returning snippets about quantum entanglement."""

    class FakeSearchEngine:
        async def buscar(self, query, max_results=5):
            results = [
                SimpleNamespace(
                    title=f"Fuente {idx}",
                    url=f"https://fuente{idx}.example/articulo",
                    snippet=f"Hallazgo {idx}: el entrelazamiento cuántico conecta partículas distantes.",
                )
                for idx in range(max_results)
            ]
            return SimpleNamespace(status="success", results=results)

    monkeypatch.setattr("cognitivo.skills.websearch_tool.WebSearchEngine", FakeSearchEngine)


@pytest.fixture
def fake_llm(monkeypatch):
    """Offline litellm.completion that records the messages of every call."""
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs["messages"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Síntesis generada"))])

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("litellm.completion", fake_completion)
    return calls


def test_create_and_list_cuadernos(cuadernos_mgr):
    nb = cuadernos_mgr.create_cuaderno("Cuaderno de Prueba", "Descripción de prueba")
    assert nb["id"] is not None
    assert nb["title"] == "Cuaderno de Prueba"

    notebooks = cuadernos_mgr.list_cuadernos()
    assert len(notebooks) == 1
    assert notebooks[0]["id"] == nb["id"]


@pytest.mark.asyncio
async def test_add_fuente_and_process(cuadernos_mgr):
    nb = cuadernos_mgr.create_cuaderno("Cuaderno RAG", "Para probar fuentes")
    file_content = b"Este es un texto de prueba sobre la arquitectura de Vision OS y LanceDB."

    fuente = await cuadernos_mgr.add_fuente(nb["id"], "test_doc.txt", file_content)
    assert fuente["filename"] == "test_doc.txt"

    src_path = str(Path(cm.SOURCES_DIR) / nb["id"] / "test_doc.txt")
    await cuadernos_mgr._process_and_index_source(nb["id"], fuente["id"], "test_doc.txt", src_path)

    notebooks = cuadernos_mgr.list_cuadernos()
    sources = notebooks[0]["sources"]
    assert len(sources) == 1
    assert sources[0]["filename"] == "test_doc.txt"
    assert sources[0]["status"] == "ready"


@pytest.mark.asyncio
async def test_investigar_y_crear_cuaderno(cuadernos_mgr, monkeypatch, fake_web_search, fake_llm):
    original_research = cuadernos_mgr._run_auto_research

    async def mock_auto_research(*args, **kwargs):
        pass

    monkeypatch.setattr(cuadernos_mgr, "_run_auto_research", mock_auto_research)
    nb = await cuadernos_mgr.investigar_y_crear_cuaderno("Física Cuántica")
    assert nb["id"] is not None
    assert nb["title"] == "Investigación: Física Cuántica"

    # Now run original research method explicitly
    await original_research(nb["id"], "Física Cuántica")
    notebooks = cuadernos_mgr.list_cuadernos()
    assert len(notebooks) == 1
    assert len(notebooks[0]["sources"]) == 1
    assert notebooks[0]["sources"][0]["status"] == "ready"
    assert len(notebooks[0]["notes"]) == 2


@pytest.mark.asyncio
async def test_auto_research_synthesizes_after_source_is_indexed(cuadernos_mgr, monkeypatch, fake_web_search, fake_llm):
    nb = cuadernos_mgr.create_cuaderno("Investigación: Física Cuántica", "Auto")
    original_index = cuadernos_mgr._process_and_index_source

    async def slow_index(*args, **kwargs):
        # Real BGE-M3 indexing on CPU takes seconds, far beyond any fixed grace period.
        await asyncio.sleep(0.5)
        await original_index(*args, **kwargs)

    monkeypatch.setattr(cuadernos_mgr, "_process_and_index_source", slow_index)

    await cuadernos_mgr._run_auto_research(nb["id"], "Física Cuántica")

    assert len(fake_llm) == 2
    for messages in fake_llm:
        system_prompt = messages[0]["content"]
        assert "entrelazamiento cuántico" in system_prompt


@pytest.mark.asyncio
async def test_generar_sintesis_keeps_metadata_written_during_llm_call(cuadernos_mgr, monkeypatch):
    nb = cuadernos_mgr.create_cuaderno("Cuaderno Concurrente", "Prueba")

    def completion_while_indexing_finishes(**kwargs):
        # Background indexing persists its metadata while the LLM call is in flight.
        metadata = cuadernos_mgr._load_metadata()
        metadata[nb["id"]]["sources"].append({"id": "src1", "filename": "doc.txt", "status": "ready", "chunks": 1})
        cuadernos_mgr._save_metadata(metadata)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Resumen"))])

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("litellm.completion", completion_while_indexing_finishes)

    await cuadernos_mgr.generar_sintesis(nb["id"], "resumen")

    stored = cuadernos_mgr.list_cuadernos()[0]
    assert [src["id"] for src in stored["sources"]] == ["src1"]
    assert len(stored["notes"]) == 1


def test_delete_cuaderno(cuadernos_mgr):
    nb = cuadernos_mgr.create_cuaderno("A eliminar", "Temporal")
    deleted = cuadernos_mgr.delete_cuaderno(nb["id"])
    assert deleted is True

    notebooks = cuadernos_mgr.list_cuadernos()
    assert len(notebooks) == 0


@pytest.mark.asyncio
async def test_chat_cuaderno_stream_params(cuadernos_mgr, monkeypatch):
    nb = cuadernos_mgr.create_cuaderno("Cuaderno Params", "Prueba de parámetros")

    # Mock WebSearchEngine
    class MockSearchResponse:
        status = "success"
        results = [
            type(
                "Item",
                (),
                {
                    "title": "Noticia Python 3.13",
                    "url": "https://example.com",
                    "snippet": "Python 3.13 incluye un nuevo JIT compiler.",
                },
            )
        ]

    class MockSearchEngine:
        async def buscar(self, query, max_results=5):
            assert max_results == 3
            return MockSearchResponse()

    monkeypatch.setattr("cognitivo.skills.websearch_tool.WebSearchEngine", MockSearchEngine)

    chunks = []
    async for chunk in cuadernos_mgr.chat_cuaderno_stream(
        notebook_id=nb["id"], query="Python 3.13 JIT", search_web=True, max_web_results=3, response_style="abierto"
    ):
        chunks.append(chunk)

    full_response = "".join(chunks)
    assert "[🌐 Buscando en la web" in full_response


@pytest.mark.asyncio
async def test_chat_cuaderno_stream_busqueda_profunda(cuadernos_mgr, monkeypatch):
    nb = cuadernos_mgr.create_cuaderno("Cuaderno Profundo", "Prueba de búsqueda profunda")

    # Mock WebSearchEngine con 22 fuentes
    class MockItem:
        def __init__(self, idx):
            self.title = f"Fuente Novedosa {idx}"
            self.url = f"https://fuente{idx}.com/articulo"
            self.snippet = f"Información relevante de la fuente {idx} sobre arquitectura cognitiva."

    class MockSearchResponseProfundo:
        status = "success"
        results = [MockItem(i) for i in range(1, 23)]

    class MockSearchEngineProfundo:
        async def buscar(self, query, max_results=5):
            assert max_results >= 20
            return MockSearchResponseProfundo()

    monkeypatch.setattr("cognitivo.skills.websearch_tool.WebSearchEngine", MockSearchEngineProfundo)

    chunks = []
    async for chunk in cuadernos_mgr.chat_cuaderno_stream(
        notebook_id=nb["id"],
        query="Arquitectura Cognitiva Avanzada",
        search_web=True,
        max_web_results=25,
        response_style="abierto",
    ):
        chunks.append(chunk)

    full_response = "".join(chunks)
    assert "modo Profunda (>20 fuentes)" in full_response

    # Verificar que se generó la nota con el informe de citas
    notebooks = cuadernos_mgr.list_cuadernos()
    active_nb = notebooks[0]
    assert len(active_nb["notes"]) == 1
    report_note = active_nb["notes"][0]
    assert report_note["type"] == "informe_profundo"
    assert "Informe de Investigación Profunda" in report_note["content"]
    assert "Total de Fuentes Consultadas**: 22" in report_note["content"]


@pytest.mark.asyncio
async def test_query_context_ignores_quote_injection_in_notebook_id(cuadernos_mgr):
    nb = cuadernos_mgr.create_cuaderno("Privado", "Fuente ajena")
    await cuadernos_mgr.add_fuente(
        nb["id"], "secreto.txt", b"Contenido confidencial del cuaderno privado.", index_in_background=False
    )

    assert cuadernos_mgr.query_cuaderno_context("nope' OR '1'='1", "contenido confidencial") == []


@pytest.mark.asyncio
async def test_add_fuente_keeps_uploaded_file_inside_notebook_dir(cuadernos_mgr, tmp_path):
    nb = cuadernos_mgr.create_cuaderno("Uploads", "Path traversal")

    fuente = await cuadernos_mgr.add_fuente(nb["id"], "../../escape.txt", b"payload", index_in_background=False)

    assert fuente["filename"] == "escape.txt"
    assert not (tmp_path / "escape.txt").exists()
    assert (tmp_path / "sources" / nb["id"] / "escape.txt").read_bytes() == b"payload"


@pytest.mark.asyncio
@pytest.mark.parametrize("notebook_id", ["..\\..\\escape", "../../escape", "no-existe"])
async def test_chat_stream_rejects_unknown_notebook_before_writing(
    cuadernos_mgr, fake_web_search, tmp_path, notebook_id
):
    with pytest.raises(cm.NotebookNotFoundError):
        async for _ in cuadernos_mgr.chat_cuaderno_stream(
            notebook_id=notebook_id, query="traversal probe zzz", search_web=True
        ):
            pass

    assert not list(tmp_path.parent.rglob("Investigacion_Web_traversal_probe_zzz*"))


@pytest.mark.asyncio
async def test_add_fuente_rejects_unknown_notebook(cuadernos_mgr, tmp_path):
    with pytest.raises(cm.NotebookNotFoundError):
        await cuadernos_mgr.add_fuente("..\\..\\escape", "a.txt", b"payload", index_in_background=False)

    assert not list(tmp_path.parent.rglob("a.txt"))


def test_delete_cuaderno_never_removes_dirs_outside_sources(cuadernos_mgr, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    metadata = cuadernos_mgr._load_metadata()
    metadata["../outside"] = {"id": "../outside", "title": "x", "sources": [], "notes": []}
    cuadernos_mgr._save_metadata(metadata)

    with pytest.raises(cm.NotebookNotFoundError):
        cuadernos_mgr.delete_cuaderno("../outside")

    assert outside.exists()


def test_chat_endpoint_returns_404_for_unknown_notebook(cuadernos_mgr, monkeypatch):
    from fastapi.testclient import TestClient

    import sentidos.sistema_periferico as gateway

    monkeypatch.setattr(gateway, "_cuadernos_mgr", cuadernos_mgr)
    client = TestClient(gateway.app)

    resp = client.post("/api/cuadernos/..%5C..%5Cescape/chat", json={"query": "hola", "search_web": True})

    assert resp.status_code == 404


def test_upload_endpoint_rejects_oversized_source(cuadernos_mgr, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    import sentidos.sistema_periferico as gateway

    monkeypatch.setattr(gateway, "_cuadernos_mgr", cuadernos_mgr)
    monkeypatch.setenv("VISION_MAX_UPLOAD_BYTES", "10")
    nb = cuadernos_mgr.create_cuaderno("Grande", "Limite de subida")

    resp = TestClient(gateway.app).post(f"/api/cuadernos/{nb['id']}/fuentes", files={"file": ("big.txt", b"x" * 11)})

    assert resp.status_code == 413
    assert cuadernos_mgr.list_cuadernos()[0]["sources"] == []
    assert not (tmp_path / "sources" / nb["id"]).exists()
