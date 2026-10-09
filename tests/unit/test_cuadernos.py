import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import cognitivo.cuadernos_manager as cm
from cognitivo.cuadernos_manager import CuadernosManager
from memoria.lancedb_manager import BGEM3Embedder

SOURCE_TEXT = b"LanceDB guarda en disco los vectores de Vision OS y responde busquedas por similitud."


async def _cuaderno_con_fuente(mgr: CuadernosManager) -> dict:
    """Notebook with one source, indexed before returning."""
    nb = mgr.create_cuaderno("Con fuente", "RAG")
    await mgr.add_fuente(nb["id"], "doc.txt", SOURCE_TEXT, index_in_background=False)
    return nb


@pytest.fixture
def router_config(monkeypatch, tmp_path):
    """Router config with one model for every effort level, so notebook calls never read the real config/."""
    path = tmp_path / "llm_router.yaml"
    path.write_text(
        "routing_strategy: pruebas\n"
        "strategies:\n"
        "  pruebas:\n"
        "    esfuerzo_bajo:\n"
        "      model: openrouter/pruebas/cuadernos\n"
        "      fallback: null\n"
        "    esfuerzo_medio:\n"
        "      model: openrouter/pruebas/cuadernos\n"
        "      fallback: null\n"
        "    esfuerzo_alto:\n"
        "      model: openrouter/pruebas/cuadernos\n"
        "      fallback: null\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("cognitivo.llm_router.CONFIG_PATH", str(path))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.fixture
def cuadernos_mgr(monkeypatch, tmp_path, router_config):
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
def failing_web_search(monkeypatch):
    """Offline WebSearchEngine whose backends all fail, like the real one without network."""

    class FailingSearchEngine:
        async def buscar(self, query, max_results=5):
            return SimpleNamespace(status="error", results=[], error="All search backends failed.")

    monkeypatch.setattr("cognitivo.skills.websearch_tool.WebSearchEngine", FailingSearchEngine)


async def _stream_chunks(*parts):
    for part in parts:
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=part))])


def _forbid_sync_completion(monkeypatch):
    """Notebook calls go through the router's async path; the blocking litellm.completion must never run."""

    def blocked(**kwargs):
        raise AssertionError("litellm.completion (sync) must not be used by notebooks")

    monkeypatch.setattr("litellm.completion", blocked)


@pytest.fixture
def fake_llm(monkeypatch, router_config):
    """Offline litellm.acompletion that records the messages of every call (streamed or not)."""
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs["messages"])
        if kwargs.get("stream"):
            return _stream_chunks("Respuesta ", "del modelo")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Síntesis generada"))])

    _forbid_sync_completion(monkeypatch)
    monkeypatch.setattr("litellm.acompletion", fake_acompletion)
    return calls


@pytest.fixture
def failing_llm(monkeypatch, router_config):
    """litellm.acompletion failing like an unreachable provider; records the messages of every call."""
    calls = []

    async def failing_completion(**kwargs):
        calls.append(kwargs["messages"])
        raise ConnectionError("proveedor LLM caído")

    _forbid_sync_completion(monkeypatch)
    monkeypatch.setattr("litellm.acompletion", failing_completion)
    return calls


@pytest.fixture
def client(cuadernos_mgr, monkeypatch):
    """Gateway test client using the temporary notebook manager."""
    from fastapi.testclient import TestClient

    import sentidos.sistema_periferico as gateway

    monkeypatch.setattr(gateway, "_cuadernos_mgr", cuadernos_mgr)
    return TestClient(gateway.app)


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
    assert cuadernos_mgr.list_cuadernos()[0]["research"]["status"] == "running"

    # Now run original research method explicitly
    await original_research(nb["id"], "Física Cuántica")
    notebooks = cuadernos_mgr.list_cuadernos()
    assert len(notebooks) == 1
    assert len(notebooks[0]["sources"]) == 1
    assert notebooks[0]["sources"][0]["status"] == "ready"
    assert len(notebooks[0]["notes"]) == 2
    assert notebooks[0]["research"] == {"status": "done", "error": None}


@pytest.mark.asyncio
async def test_auto_research_without_web_results_records_error_instead_of_placeholder(
    cuadernos_mgr, failing_web_search, fake_llm
):
    nb = cuadernos_mgr.create_cuaderno("Investigación: Nada", "Auto")

    await cuadernos_mgr._run_auto_research(nb["id"], "Nada")

    stored = cuadernos_mgr.list_cuadernos()[0]
    assert stored["sources"] == []
    assert stored["notes"] == []
    assert stored["research"]["status"] == "error"
    assert "All search backends failed" in stored["research"]["error"]
    assert fake_llm == []


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
    nb = await _cuaderno_con_fuente(cuadernos_mgr)

    async def completion_while_indexing_finishes(**kwargs):
        # Background indexing persists its metadata while the LLM call is in flight.
        metadata = cuadernos_mgr._load_metadata()
        metadata[nb["id"]]["sources"].append({"id": "src1", "filename": "doc2.txt", "status": "ready", "chunks": 1})
        cuadernos_mgr._save_metadata(metadata)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Resumen"))])

    _forbid_sync_completion(monkeypatch)
    monkeypatch.setattr("litellm.acompletion", completion_while_indexing_finishes)

    await cuadernos_mgr.generar_sintesis(nb["id"], "resumen")

    stored = cuadernos_mgr.list_cuadernos()[0]
    assert [src["filename"] for src in stored["sources"]] == ["doc.txt", "doc2.txt"]
    assert len(stored["notes"]) == 1


@pytest.mark.asyncio
async def test_generar_sintesis_raises_when_llm_fails_and_saves_no_note(cuadernos_mgr, failing_llm):
    nb = await _cuaderno_con_fuente(cuadernos_mgr)

    with pytest.raises(cm.NotebookLLMError, match="proveedor LLM caído"):
        await cuadernos_mgr.generar_sintesis(nb["id"], "resumen")

    assert cuadernos_mgr.list_cuadernos()[0]["notes"] == []


@pytest.mark.asyncio
async def test_generar_sintesis_on_empty_notebook_raises_without_calling_llm(cuadernos_mgr, fake_llm):
    nb = cuadernos_mgr.create_cuaderno("Vacío", "Sin fuentes")

    with pytest.raises(cm.EmptyNotebookError):
        await cuadernos_mgr.generar_sintesis(nb["id"], "resumen")

    assert fake_llm == []
    assert cuadernos_mgr.list_cuadernos()[0]["notes"] == []


def test_delete_cuaderno(cuadernos_mgr):
    nb = cuadernos_mgr.create_cuaderno("A eliminar", "Temporal")
    deleted = cuadernos_mgr.delete_cuaderno(nb["id"])
    assert deleted is True

    notebooks = cuadernos_mgr.list_cuadernos()
    assert len(notebooks) == 0


@pytest.mark.asyncio
async def test_chat_cuaderno_stream_params(cuadernos_mgr, monkeypatch, fake_llm):
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
    assert full_response.endswith("Respuesta del modelo")
    # The answer is grounded on the source the web search just indexed.
    assert "Python 3.13 incluye un nuevo JIT compiler." in fake_llm[0][0]["content"]


@pytest.mark.asyncio
async def test_chat_raises_when_llm_fails_instead_of_answering_with_raw_chunks(cuadernos_mgr, failing_llm):
    nb = await _cuaderno_con_fuente(cuadernos_mgr)
    received = []

    with pytest.raises(cm.NotebookLLMError, match="proveedor LLM caído"):
        async for chunk in cuadernos_mgr.chat_cuaderno_stream(nb["id"], "¿Dónde guarda los vectores?"):
            received.append(chunk)

    assert received == []


@pytest.mark.asyncio
async def test_chat_on_empty_notebook_raises_without_calling_llm(cuadernos_mgr, fake_llm):
    nb = cuadernos_mgr.create_cuaderno("Vacío", "Sin fuentes")

    with pytest.raises(cm.EmptyNotebookError):
        async for _ in cuadernos_mgr.chat_cuaderno_stream(nb["id"], "hola"):
            pass

    assert fake_llm == []


@pytest.mark.asyncio
async def test_chat_reports_failed_web_search(cuadernos_mgr, failing_web_search, fake_llm):
    nb = await _cuaderno_con_fuente(cuadernos_mgr)

    with pytest.raises(cm.WebSearchError, match="All search backends failed"):
        async for _ in cuadernos_mgr.chat_cuaderno_stream(nb["id"], "@web novedades", search_web=True):
            pass

    assert fake_llm == []
    assert len(cuadernos_mgr.list_cuadernos()[0]["sources"]) == 1


@pytest.mark.asyncio
async def test_chat_cuaderno_stream_busqueda_profunda(cuadernos_mgr, monkeypatch, fake_llm):
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

    # The report note is written by the LLM from every search result, not filled into a template.
    active_nb = cuadernos_mgr.list_cuadernos()[0]
    assert len(active_nb["notes"]) == 1
    report_note = active_nb["notes"][0]
    assert report_note["type"] == "informe_profundo"
    assert report_note["content"] == "Síntesis generada"
    report_prompt = fake_llm[0][0]["content"]
    assert "Fuente Novedosa 1" in report_prompt
    assert "Fuente Novedosa 22" in report_prompt


@pytest.mark.asyncio
async def test_deep_search_saves_no_report_when_llm_fails(cuadernos_mgr, fake_web_search, failing_llm):
    nb = cuadernos_mgr.create_cuaderno("Profundo", "Sin LLM")

    with pytest.raises(cm.NotebookLLMError):
        async for _ in cuadernos_mgr.chat_cuaderno_stream(
            nb["id"], "entrelazamiento", search_web=True, max_web_results=25
        ):
            pass

    stored = cuadernos_mgr.list_cuadernos()[0]
    assert stored["notes"] == []
    # The web findings are real, so the indexed source stays.
    assert [src["status"] for src in stored["sources"]] == ["ready"]


@pytest.mark.asyncio
async def test_query_context_ignores_quote_injection_in_notebook_id(cuadernos_mgr):
    nb = cuadernos_mgr.create_cuaderno("Privado", "Fuente ajena")
    await cuadernos_mgr.add_fuente(
        nb["id"], "secreto.txt", b"Contenido confidencial del cuaderno privado.", index_in_background=False
    )

    assert cuadernos_mgr.query_cuaderno_context("nope' OR '1'='1", "contenido confidencial") == []


def test_query_context_raises_when_search_fails(cuadernos_mgr, monkeypatch):
    # A failed search must not look like an empty notebook.
    class BrokenTable:
        def search(self, *args, **kwargs):
            raise RuntimeError("tabla LanceDB corrupta")

    monkeypatch.setattr(cuadernos_mgr.db, "open_table", lambda name: BrokenTable())

    with pytest.raises(RuntimeError, match="tabla LanceDB corrupta"):
        cuadernos_mgr.query_cuaderno_context("abc12345", "consulta")


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


def test_chat_endpoint_returns_409_for_empty_notebook(cuadernos_mgr, client, fake_llm):
    nb = cuadernos_mgr.create_cuaderno("Vacío", "Sin fuentes")

    resp = client.post(f"/api/cuadernos/{nb['id']}/chat", json={"query": "hola"})

    assert resp.status_code == 409
    assert resp.json()["status"] == "error"
    assert fake_llm == []


def test_chat_endpoint_returns_502_when_llm_fails(cuadernos_mgr, client, failing_llm):
    nb = asyncio.run(_cuaderno_con_fuente(cuadernos_mgr))

    resp = client.post(f"/api/cuadernos/{nb['id']}/chat", json={"query": "¿Dónde guarda los vectores?"})

    assert resp.status_code == 502
    assert resp.json()["status"] == "error"
    assert "proveedor LLM caído" in resp.json()["message"]


def test_chat_endpoint_ends_a_started_stream_with_an_error_event(cuadernos_mgr, client, fake_web_search, failing_llm):
    from sentidos.sistema_periferico import CHAT_STREAM_ERROR_MARKER

    nb = cuadernos_mgr.create_cuaderno("Web", "Falla a mitad")

    resp = client.post(f"/api/cuadernos/{nb['id']}/chat", json={"query": "entrelazamiento", "search_web": True})

    assert resp.status_code == 200
    answer, marker, event = resp.text.partition(CHAT_STREAM_ERROR_MARKER)
    assert marker == CHAT_STREAM_ERROR_MARKER
    assert answer.startswith("[🌐 Buscando en la web")
    assert "Hallazgo" not in answer
    error = json.loads(event)
    assert error["status"] == "error"
    assert "proveedor LLM caído" in error["message"]


def test_chat_endpoint_ends_stream_with_error_when_web_search_finds_nothing(
    cuadernos_mgr, client, failing_web_search, fake_llm
):
    from sentidos.sistema_periferico import CHAT_STREAM_ERROR_MARKER

    nb = asyncio.run(_cuaderno_con_fuente(cuadernos_mgr))

    resp = client.post(f"/api/cuadernos/{nb['id']}/chat", json={"query": "@web novedades"})

    assert resp.status_code == 200
    answer, marker, event = resp.text.partition(CHAT_STREAM_ERROR_MARKER)
    assert marker == CHAT_STREAM_ERROR_MARKER
    assert answer.startswith("[🌐 Buscando en la web")
    assert "All search backends failed" in json.loads(event)["message"]
    assert fake_llm == []
    assert len(cuadernos_mgr.list_cuadernos()[0]["sources"]) == 1


def test_sintesis_endpoint_maps_notebook_errors_to_http_status(cuadernos_mgr, client, failing_llm):
    empty = cuadernos_mgr.create_cuaderno("Vacío", "Sin fuentes")
    with_source = asyncio.run(_cuaderno_con_fuente(cuadernos_mgr))

    assert client.post("/api/cuadernos/no-existe/sintesis", json={"tipo": "resumen"}).status_code == 404
    assert client.post(f"/api/cuadernos/{empty['id']}/sintesis", json={"tipo": "resumen"}).status_code == 409
    resp = client.post(f"/api/cuadernos/{with_source['id']}/sintesis", json={"tipo": "resumen"})
    assert resp.status_code == 502
    assert "proveedor LLM caído" in resp.json()["message"]
    assert all(nb["notes"] == [] for nb in cuadernos_mgr.list_cuadernos())


def _spy_on_router(cuadernos_mgr, monkeypatch):
    """Records (kind, effort, api_key) of every router call the notebooks make; the router itself still runs."""
    calls = []
    router = cuadernos_mgr.llm
    original_complete = router.complete_messages
    original_stream = router.stream_messages

    async def complete_spy(effort, messages, api_key=None):
        calls.append(("complete", effort, api_key))
        return await original_complete(effort, messages, api_key=api_key)

    def stream_spy(effort, messages, api_key=None):
        calls.append(("stream", effort, api_key))
        return original_stream(effort, messages, api_key=api_key)

    monkeypatch.setattr(router, "complete_messages", complete_spy)
    monkeypatch.setattr(router, "stream_messages", stream_spy)
    return calls


@pytest.mark.asyncio
async def test_notebook_model_comes_from_the_router_config(cuadernos_mgr, monkeypatch):
    nb = await _cuaderno_con_fuente(cuadernos_mgr)
    models = []

    async def completion(**kwargs):
        models.append(kwargs["model"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Resumen"))])

    _forbid_sync_completion(monkeypatch)
    monkeypatch.setattr("litellm.acompletion", completion)

    await cuadernos_mgr.generar_sintesis(nb["id"], "resumen")

    assert models == ["openrouter/pruebas/cuadernos"]


@pytest.mark.asyncio
async def test_synthesis_asks_the_router_for_high_effort_with_the_caller_key(cuadernos_mgr, monkeypatch, fake_llm):
    nb = await _cuaderno_con_fuente(cuadernos_mgr)
    calls = _spy_on_router(cuadernos_mgr, monkeypatch)

    await cuadernos_mgr.generar_sintesis(nb["id"], "resumen", "sk-usuario")

    assert calls == [("complete", "esfuerzo_alto", "sk-usuario")]


@pytest.mark.asyncio
async def test_chat_streams_through_the_router_with_medium_effort(cuadernos_mgr, monkeypatch, fake_llm):
    nb = await _cuaderno_con_fuente(cuadernos_mgr)
    calls = _spy_on_router(cuadernos_mgr, monkeypatch)

    chunks = [
        chunk
        async for chunk in cuadernos_mgr.chat_cuaderno_stream(
            nb["id"], "¿Dónde guarda los vectores?", provider_api_key="sk-usuario"
        )
    ]

    assert "".join(chunks) == "Respuesta del modelo"
    assert calls == [("stream", "esfuerzo_medio", "sk-usuario")]
