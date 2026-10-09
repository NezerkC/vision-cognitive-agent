"""The voice loop: spoken requests enter through the Amígdala like typed ones, and their answers are spoken back."""

import asyncio

import pytest

from cognitivo.puente_voz import PuenteVoz
from core.adapters.event_bus_inmemory import AsyncInMemoryEventBus
from core.amigdala import Amigdala


class Recorder(list):
    """(topic, data) pairs the bridge published."""

    async def __call__(self, topic: str, data: dict) -> None:
        self.append((topic, data))

    def on(self, topic: str) -> list[dict]:
        return [data for name, data in self if name == topic]


def _transcription(text: str) -> dict:
    return {"transcripcion": text, "timestamp": 0.0}


@pytest.mark.asyncio
async def test_spoken_request_enters_the_cognitive_input_with_a_voice_id():
    bridge, published = PuenteVoz(), Recorder()

    await bridge.handle_event("canal.sensorial.audio.transcripcion", _transcription("¿qué hora es?"), published)

    [request] = published.on("canal.cognitivo.entrada")
    assert request["request_id"].startswith("voz-")
    assert request["prompt"] == "¿qué hora es?"
    assert len(published) == 1


@pytest.mark.asyncio
async def test_blank_transcription_is_not_forwarded():
    bridge, published = PuenteVoz(), Recorder()

    await bridge.handle_event("canal.sensorial.audio.transcripcion", _transcription("   "), published)

    assert published == []


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["si, procede a investigar por favor", "no, abortar investigacion"])
async def test_answer_to_a_pending_intriga_ticket_is_not_a_request(answer):
    bridge, published = PuenteVoz(), Recorder()
    await bridge.handle_event("canal.intriga.estado", {"esperando_confirmacion": True}, published)

    await bridge.handle_event("canal.sensorial.audio.transcripcion", _transcription(answer), published)

    assert published.on("canal.cognitivo.entrada") == []


@pytest.mark.asyncio
async def test_other_speech_is_a_request_while_a_ticket_is_pending():
    bridge, published = PuenteVoz(), Recorder()
    await bridge.handle_event("canal.intriga.estado", {"esperando_confirmacion": True}, published)

    await bridge.handle_event("canal.sensorial.audio.transcripcion", _transcription("hola"), published)

    assert len(published.on("canal.cognitivo.entrada")) == 1


@pytest.mark.asyncio
async def test_approval_words_are_a_request_when_no_ticket_is_pending():
    bridge, published = PuenteVoz(), Recorder()
    await bridge.handle_event("canal.intriga.estado", {"esperando_confirmacion": True}, published)
    await bridge.handle_event("canal.intriga.estado", {"esperando_confirmacion": False}, published)

    await bridge.handle_event("canal.sensorial.audio.transcripcion", _transcription("sí"), published)

    assert len(published.on("canal.cognitivo.entrada")) == 1


@pytest.mark.asyncio
async def test_voice_answer_is_spoken_back():
    bridge, published = PuenteVoz(), Recorder()
    response = {"request_id": "voz-1", "response": "Son las tres.", "status": "success", "model_used": "x"}

    await bridge.handle_event("canal.cognitivo.respuesta", response, published)

    assert published == [("canal.sensorial.audio.hablar", {"texto": "Son las tres."})]


@pytest.mark.asyncio
async def test_answers_to_other_requests_are_not_spoken():
    bridge, published = PuenteVoz(), Recorder()
    response = {"request_id": "intriga-search-formulation-1", "response": "x", "status": "success"}

    await bridge.handle_event("canal.cognitivo.respuesta", response, published)

    assert published == []


@pytest.mark.asyncio
async def test_failed_voice_request_is_apologised_for_and_announced_with_its_error():
    bridge, published = PuenteVoz(), Recorder()
    failure = {"request_id": "voz-2", "error": "LLM caído", "status": "failed"}

    await bridge.handle_event("canal.cognitivo.respuesta", failure, published)

    assert published.on("canal.sensorial.audio.hablar") == [{"texto": "No pude responder a eso."}]
    [announcement] = published.on("canal.sistema.anuncios")
    assert "LLM caído" in announcement["mensaje"]


@pytest.mark.asyncio
async def test_blocked_voice_request_is_spoken_and_announced():
    bridge, published = PuenteVoz(), Recorder()
    alert = {"request_id": "voz-3", "status": "BLOCKED", "reason": "Prompt injection signature detected: sudo "}

    await bridge.handle_event("canal.seguridad.alerta", alert, published)

    assert len(published.on("canal.sensorial.audio.hablar")) == 1
    [announcement] = published.on("canal.sistema.anuncios")
    assert "sudo" in announcement["mensaje"]


@pytest.mark.asyncio
async def test_alerts_for_typed_requests_are_left_to_the_hud():
    bridge, published = PuenteVoz(), Recorder()

    await bridge.handle_event("canal.seguridad.alerta", {"request_id": "manual-1", "status": "BLOCKED"}, published)

    assert published == []


@pytest.mark.asyncio
async def test_spoken_prompt_goes_through_the_amigdala_on_the_event_bus():
    """Wires the bridge, the in-memory bus and the Amígdala the way the orchestrator does."""
    bus = AsyncInMemoryEventBus()
    amigdala = Amigdala()
    bridge = PuenteVoz()
    seen: list[tuple[str, dict]] = []
    arrived = asyncio.Event()

    async def amigdala_input(topic: str, data: dict) -> None:
        await amigdala.handle_cognitive_input(data, bus.publish)

    async def record(topic: str, data: dict) -> None:
        seen.append((topic, data))
        arrived.set()

    async def bridge_transcription(topic: str, data: dict) -> None:
        await bridge.handle_event(topic, data, bus.publish)

    try:
        await bus.subscribe(["canal.cognitivo.entrada"], amigdala_input)
        await bus.subscribe(["canal.cognitivo.peticion", "canal.seguridad.alerta"], record)
        await bus.subscribe(["canal.sensorial.audio.transcripcion"], bridge_transcription)

        await bus.publish("canal.sensorial.audio.transcripcion", _transcription("abre el navegador"))
        await asyncio.wait_for(arrived.wait(), 2)

        [(topic, request)] = seen
        assert topic == "canal.cognitivo.peticion"
        assert request["request_id"].startswith("voz-")
        assert request["prompt"] == "abre el navegador"
    finally:
        await bus.shutdown()
