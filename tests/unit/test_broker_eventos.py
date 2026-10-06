"""Unit tests for EventBroker TCP bus."""

import asyncio
import json

import pytest

from core.broker_eventos import EventBroker
from core.schemas import EventEnvelope


@pytest.mark.unit
def test_event_envelope_validation():
    """EventEnvelope validates incoming payload structure."""
    envelope = EventEnvelope.validate_payload(topic="canal.memoria", data={"action": "guardar", "text": "Test memory"})
    assert envelope.topic == "canal.memoria"
    assert envelope.data["action"] == "guardar"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_broker_instantiation():
    """EventBroker initializes with correct host and port."""
    broker = EventBroker(host="127.0.0.1", port=0)
    assert broker.host == "127.0.0.1"
    assert broker.subscriptions == {}


EXECUTOR_ACTION = {
    "action": "publish",
    "topic": "canal.ejecucion.accion",
    "data": {"herramienta": "ejecutar_script", "parametros": ["calc.exe"]},
}


async def _start_broker():
    broker = EventBroker(port=0)
    server = await asyncio.start_server(broker.handle_client, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


async def _connect(port):
    return await asyncio.open_connection("127.0.0.1", port)


async def _subscribe(port, topic):
    reader, writer = await _connect(port)
    writer.write((json.dumps({"action": "subscribe", "topics": [topic]}) + "\n").encode())
    await writer.drain()
    await asyncio.sleep(0.1)
    return reader, writer


async def _received_topics(reader, timeout=0.5):
    topics = []
    try:
        while line := await asyncio.wait_for(reader.readline(), timeout):
            topics.append(json.loads(line).get("topic"))
    except TimeoutError:
        pass
    return topics


@pytest.mark.unit
@pytest.mark.asyncio
async def test_json_client_publish_reaches_subscribers():
    server, port = await _start_broker()
    sub_reader, sub_writer = await _subscribe(port, "canal.ejecucion.accion")
    _, publisher = await _connect(port)

    publisher.write((json.dumps(EXECUTOR_ACTION) + "\n").encode())
    await publisher.drain()

    assert "canal.ejecucion.accion" in await _received_topics(sub_reader)
    for writer in (sub_writer, publisher):
        writer.close()
    server.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_http_request_from_a_browser_cannot_smuggle_events():
    """A web page can POST text/plain to 127.0.0.1:5000; its JSON body must not become an event."""
    server, port = await _start_broker()
    sub_reader, sub_writer = await _subscribe(port, "canal.ejecucion.accion")
    attacker_reader, attacker = await _connect(port)
    body = json.dumps(EXECUTOR_ACTION)

    attacker.write(
        (
            "POST / HTTP/1.1\r\nHost: 127.0.0.1:5000\r\nOrigin: https://evil.example\r\n"
            f"Content-Type: text/plain\r\nContent-Length: {len(body) + 1}\r\n\r\n{body}\n"
        ).encode()
    )
    await attacker.drain()

    assert "canal.ejecucion.accion" not in await _received_topics(sub_reader)
    assert await asyncio.wait_for(attacker_reader.read(), 1) == b""  # connection closed by the broker
    for writer in (sub_writer, attacker):
        writer.close()
    server.close()
