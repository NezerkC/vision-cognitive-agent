import json

import pytest

from cognitivo.contexto_derecho import ContextoDerecho

SCREENSHOT = {"image": "aW1hZ2Vu", "timestamp": 1700000000.7, "mock": False}
REQUEST_ID = "derecho-1700000000"


class FakeWriter:
    def __init__(self):
        self.events = []

    def write(self, data: bytes):
        self.events.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        pass


@pytest.fixture
def derecho():
    return ContextoDerecho()


@pytest.mark.asyncio
async def test_screenshot_asks_the_llm_to_analyze_the_image(derecho):
    writer = FakeWriter()

    await derecho.handle_event("canal.sensorial.vision", SCREENSHOT, writer)

    [event] = writer.events
    assert event["topic"] == "canal.cognitivo.entrada"
    request = event["data"]
    assert request["request_id"] == REQUEST_ID
    assert request["image_base64"] == "aW1hZ2Vu"
    assert request["prompt"]
    assert "mock" not in request
    assert REQUEST_ID in derecho.pending_requests


@pytest.mark.asyncio
async def test_vision_event_without_an_image_publishes_nothing(derecho):
    writer = FakeWriter()

    await derecho.handle_event("canal.sensorial.vision", {"timestamp": 1700000000.7}, writer)

    assert writer.events == []
    assert derecho.pending_requests == {}


@pytest.mark.asyncio
async def test_successful_analysis_publishes_the_screen_context(derecho):
    writer = FakeWriter()
    await derecho.handle_event("canal.sensorial.vision", SCREENSHOT, writer)

    await derecho.handle_event(
        "canal.cognitivo.respuesta",
        {"request_id": REQUEST_ID, "status": "success", "response": "El usuario edita código en VS Code"},
        writer,
    )

    context = writer.events[-1]
    assert context["topic"] == "canal.sistema.contexto_actual"
    assert context["data"]["contexto"] == "El usuario edita código en VS Code"
    assert derecho.pending_requests == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {"request_id": REQUEST_ID, "status": "failed", "error": "LLM caído"},
        {"request_id": REQUEST_ID, "status": "success", "response": ""},
    ],
)
async def test_failed_analysis_publishes_nothing(derecho, response):
    writer = FakeWriter()
    await derecho.handle_event("canal.sensorial.vision", SCREENSHOT, writer)
    writer.events.clear()

    await derecho.handle_event("canal.cognitivo.respuesta", response, writer)

    assert writer.events == []
    assert derecho.pending_requests == {}


@pytest.mark.asyncio
async def test_purge_forgets_pending_requests(derecho):
    writer = FakeWriter()
    await derecho.handle_event("canal.sensorial.vision", SCREENSHOT, writer)

    await derecho.handle_event("system", {"action": "purge"}, writer)
    writer.events.clear()
    await derecho.handle_event(
        "canal.cognitivo.respuesta",
        {"request_id": REQUEST_ID, "status": "success", "response": "Respuesta tardía"},
        writer,
    )

    assert derecho.pending_requests == {}
    assert writer.events == []
