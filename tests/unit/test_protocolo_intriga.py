import inspect
import json

import pytest

import cognitivo.protocolo_intriga as pi
from cognitivo.protocolo_intriga import ProtocoloIntriga
from cognitivo.skills.websearch_tool import SearchResponse, SearchResult

PERMISSION_PHRASE = "¿Me das permiso para crear un ticket de situación"


class FakeWriter:
    def __init__(self):
        self.events = []

    def write(self, data: bytes):
        self.events.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        pass

    def topics(self):
        return [e["topic"] for e in self.events]


def _engine(response: SearchResponse):
    class FakeEngine:
        queries = []

        async def buscar(self, query, max_results=5):
            FakeEngine.queries.append(query)
            return response

    return FakeEngine


FOUND = SearchResponse(
    status="success",
    results=[SearchResult("Fix for FFmpeg crash", "https://example.com/fix", "Reinstall the codec pack.")],
    source="duckduckgo",
)
NOTHING = SearchResponse(status="error", results=[], source="duckduckgo", error="all backends failed")


def test_intriga_has_no_mock_flag():
    assert "is_mock" not in inspect.signature(ProtocoloIntriga).parameters
    assert not hasattr(ProtocoloIntriga(), "is_mock")


@pytest.mark.asyncio
async def test_anomaly_asks_for_permission_before_researching():
    intriga, writer = ProtocoloIntriga(), FakeWriter()

    await intriga.process_context("ANOMALIA_DETECTADA: FFmpeg crashed", writer)

    assert intriga.waiting_for_confirmation
    assert "canal.cognitivo.peticion" not in writer.topics()
    announcement = next(e["data"] for e in writer.events if e["topic"] == "canal.sistema.anuncios")
    assert PERMISSION_PHRASE in announcement["mensaje"]
    assert announcement["error_original"] == "FFmpeg crashed"


@pytest.mark.asyncio
async def test_approval_starts_the_research():
    intriga, writer = ProtocoloIntriga(), FakeWriter()
    await intriga.process_context("ANOMALIA_DETECTADA: FFmpeg crashed", writer)

    await intriga.handle_transcription("si, procede a investigar por favor", writer)

    assert not intriga.waiting_for_confirmation
    request = next(e["data"] for e in writer.events if e["topic"] == "canal.cognitivo.peticion")
    assert request["request_id"].startswith("intriga-search-formulation-")
    assert "FFmpeg crashed" in request["prompt"]


@pytest.mark.asyncio
async def test_rejection_closes_the_ticket_without_researching():
    intriga, writer = ProtocoloIntriga(), FakeWriter()
    await intriga.process_context("ANOMALIA_DETECTADA: FFmpeg crashed", writer)

    await intriga.handle_transcription("no, abortar investigacion", writer)

    assert not intriga.waiting_for_confirmation
    assert intriga.active_error is None
    assert "canal.cognitivo.peticion" not in writer.topics()


@pytest.mark.asyncio
async def test_transcriptions_are_ignored_when_no_ticket_is_pending():
    intriga, writer = ProtocoloIntriga(), FakeWriter()

    await intriga.handle_transcription("si, dale", writer)

    assert writer.events == []


@pytest.mark.asyncio
async def test_pending_ticket_is_published_before_the_question():
    """The voice loop reads this state to tell "sí, procede" answers apart from new requests."""
    intriga, writer = ProtocoloIntriga(), FakeWriter()

    await intriga.process_context("ANOMALIA_DETECTADA: FFmpeg crashed", writer)

    assert writer.topics()[0] == "canal.intriga.estado"
    assert writer.events[0]["data"] == {"esperando_confirmacion": True}
    assert writer.topics()[1] == "canal.sistema.anuncios"


@pytest.mark.asyncio
async def test_answering_the_ticket_publishes_that_it_is_no_longer_pending():
    intriga, writer = ProtocoloIntriga(), FakeWriter()
    await intriga.process_context("ANOMALIA_DETECTADA: FFmpeg crashed", writer)

    await intriga.handle_transcription("no, abortar investigacion", writer)

    states = [e["data"] for e in writer.events if e["topic"] == "canal.intriga.estado"]
    assert states == [{"esperando_confirmacion": True}, {"esperando_confirmacion": False}]


@pytest.mark.asyncio
async def test_found_solution_is_saved_with_its_sources(monkeypatch):
    monkeypatch.setattr(pi, "WebSearchEngine", _engine(FOUND))
    intriga, writer = ProtocoloIntriga(), FakeWriter()
    intriga.active_error = "FFmpeg crashed"

    await intriga.handle_llm_response("intriga-search-formulation-1", "ffmpeg crash windows fix", writer)

    memory = next(e["data"] for e in writer.events if e["topic"] == "canal.memoria")
    assert "Reinstall the codec pack." in memory["text"]
    assert "https://example.com/fix" in memory["text"]


@pytest.mark.asyncio
async def test_no_solution_is_reported_and_nothing_is_saved(monkeypatch):
    monkeypatch.setattr(pi, "WebSearchEngine", _engine(NOTHING))
    intriga, writer = ProtocoloIntriga(), FakeWriter()
    intriga.active_error = "FFmpeg crashed"

    await intriga.handle_llm_response("intriga-search-formulation-1", "ffmpeg crash windows fix", writer)

    assert "canal.memoria" not in writer.topics()
    assert "canal.sistema.anuncios" in writer.topics()
    assert intriga.active_error is None


@pytest.mark.asyncio
async def test_capacitacion_stops_when_no_documentation_is_found(monkeypatch):
    monkeypatch.setattr(pi, "WebSearchEngine", _engine(NOTHING))
    writer = FakeWriter()

    await ProtocoloIntriga().iniciar_protocolo_capacitacion("git", writer)

    assert "canal.cognitivo.peticion" not in writer.topics()


def test_no_simulated_solutions_remain():
    source = inspect.getsource(pi)

    assert "Solución Simulada" not in source
    assert "Solución alternativa" not in source
