"""
TCP Socket Bridge Adapter for Visión OS Event Bus.
Enables backward-compatible TCP socket connections on port 5000 bridged to the in-memory bus.
"""

import asyncio
import json
import logging
from typing import Any

from core.ports.event_bus import IEventBus

logger = logging.getLogger("TCPEventBusBridge")


class TCPEventBusBridge:
    """
    Bridges external TCP socket clients to the internal high-performance IEventBus.
    Preserves backwards compatibility for scripts or tools communicating over TCP.
    """

    def __init__(self, event_bus: IEventBus, host: str = "127.0.0.1", port: int = 5000):
        self.event_bus = event_bus
        self.host = host
        self.port = port
        self.server: asyncio.Server | None = None
        self._client_subscriptions: dict[asyncio.StreamWriter, str] = {}

    async def start(self) -> None:
        """Starts the TCP socket server bridge."""
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port, limit=16 * 1024 * 1024)
        addr = self.server.sockets[0].getsockname()
        logger.info(f"Serving TCP Event Bus Bridge on {addr}")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        client_addr = writer.get_extra_info("peername")
        logger.info(f"TCP Bridge client connected from {client_addr}")

        # Forwarder handler sending in-memory bus events over this client's TCP socket
        async def forward_to_tcp(topic: str, data: dict[str, Any]) -> None:
            try:
                msg = {"topic": topic, "data": data}
                line = json.dumps(msg) + "\n"
                writer.write(line.encode("utf-8"))
                await writer.drain()
            except Exception as e:
                logger.debug(f"Failed to forward event to TCP client {client_addr}: {e}")

        sub_id: str | None = None

        try:
            while True:
                line_bytes = await reader.readline()
                if not line_bytes:
                    break

                text = line_bytes.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    msg = None
                if not isinstance(msg, dict):
                    # Clients speak JSON-object lines only. Dropping the connection (instead of skipping the line)
                    # stops cross-protocol attacks: a web page can POST to this port, and after its HTTP header
                    # lines were skipped, its JSON body would have been processed as a legitimate event.
                    logger.warning(f"Non-JSON-object input from {client_addr}; closing connection.")
                    break

                action = msg.get("action")
                if action == "publish":
                    topic = msg.get("topic")
                    data = msg.get("data", {})
                    if topic:
                        await self.event_bus.publish(topic, data)

                elif action == "subscribe":
                    topics = msg.get("topics", [])
                    if isinstance(topics, list) and topics:
                        if sub_id:
                            await self.event_bus.unsubscribe(sub_id)
                        sub_id = await self.event_bus.subscribe(topics, forward_to_tcp)
                        self._client_subscriptions[writer] = sub_id

                elif action == "unsubscribe":
                    if sub_id:
                        await self.event_bus.unsubscribe(sub_id)
                        sub_id = None

                elif action == "purge":
                    await self.event_bus.purge()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error handling TCP Bridge client {client_addr}: {e}")
        finally:
            if sub_id:
                await self.event_bus.unsubscribe(sub_id)
                self._client_subscriptions.pop(writer, None)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info(f"TCP Bridge client disconnected from {client_addr}")

    async def stop(self) -> None:
        """Stops the TCP socket bridge server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("TCP Event Bus Bridge stopped.")
