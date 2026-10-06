import asyncio
import json

import pytest

from core.adapters.event_bus_inmemory import AsyncInMemoryEventBus
from core.adapters.event_bus_tcp_bridge import TCPEventBusBridge

EXECUTOR_ACTION = {
    "action": "publish",
    "topic": "canal.ejecucion.accion",
    "data": {"request_id": "r1", "herramienta": "ejecutar_script", "parametros": ["calc.exe"]},
}


@pytest.fixture
async def bridge_and_received():
    bus = AsyncInMemoryEventBus()
    received = []

    async def capture(topic, data):
        received.append(topic)

    await bus.subscribe(["canal.ejecucion.accion"], capture)
    bridge = TCPEventBusBridge(bus, host="127.0.0.1", port=0)
    await bridge.start()
    port = bridge.server.sockets[0].getsockname()[1]
    yield port, received
    await bridge.stop()
    await bus.shutdown()


@pytest.mark.asyncio
async def test_json_client_publish_reaches_the_bus(bridge_and_received):
    port, received = bridge_and_received
    _, writer = await asyncio.open_connection("127.0.0.1", port)

    writer.write((json.dumps(EXECUTOR_ACTION) + "\n").encode())
    await writer.drain()
    await asyncio.sleep(0.3)

    assert received == ["canal.ejecucion.accion"]
    writer.close()


@pytest.mark.asyncio
async def test_http_request_from_a_browser_cannot_smuggle_events(bridge_and_received):
    """A web page can POST text/plain to 127.0.0.1:5000; its JSON body must not become an event."""
    port, received = bridge_and_received
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    body = json.dumps(EXECUTOR_ACTION)

    writer.write(
        (
            "POST / HTTP/1.1\r\nHost: 127.0.0.1:5000\r\nOrigin: https://evil.example\r\n"
            f"Content-Type: text/plain\r\nContent-Length: {len(body) + 1}\r\n\r\n{body}\n"
        ).encode()
    )
    await writer.drain()
    await asyncio.sleep(0.3)

    assert received == []
    assert await asyncio.wait_for(reader.read(), 1) == b""  # connection closed by the bridge
    writer.close()
