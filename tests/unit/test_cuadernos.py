import shutil
from pathlib import Path

import pytest

import cognitivo.cuadernos_manager as cm
from cognitivo.cuadernos_manager import CuadernosManager


@pytest.fixture
def cuadernos_mgr(monkeypatch):
    c_dir = Path(__file__).parent.parent / "temp_test_cuadernos"
    if c_dir.exists():
        shutil.rmtree(c_dir, ignore_errors=True)
    c_dir.mkdir(parents=True, exist_ok=True)
    
    monkeypatch.setattr("cognitivo.cuadernos_manager.CUADERNOS_DIR", str(c_dir))
    monkeypatch.setattr("cognitivo.cuadernos_manager.METADATA_FILE", str(c_dir / "notebooks.json"))
    monkeypatch.setattr("cognitivo.cuadernos_manager.SOURCES_DIR", str(c_dir / "sources"))
    monkeypatch.setattr("cognitivo.cuadernos_manager.LANCE_DB_PATH", str(c_dir / "lancedb_cuadernos"))
    
    mgr = CuadernosManager()
    yield mgr

    shutil.rmtree(c_dir, ignore_errors=True)

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
async def test_investigar_y_crear_cuaderno(cuadernos_mgr, monkeypatch):
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
    assert len(notebooks[0]["notes"]) == 2

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
            type("Item", (), {"title": "Noticia Python 3.13", "url": "https://example.com", "snippet": "Python 3.13 incluye un nuevo JIT compiler."})
        ]

    class MockSearchEngine:
        async def buscar(self, query, max_results=5):
            assert max_results == 3
            return MockSearchResponse()

    monkeypatch.setattr("cognitivo.skills.websearch_tool.WebSearchEngine", MockSearchEngine)

    chunks = []
    async for chunk in cuadernos_mgr.chat_cuaderno_stream(
        notebook_id=nb["id"],
        query="Python 3.13 JIT",
        search_web=True,
        max_web_results=3,
        response_style="abierto"
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
        response_style="abierto"
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


