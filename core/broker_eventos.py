import asyncio
import json
import logging
import sys

try:
    from core.schemas import EventEnvelope
except ImportError:
    EventEnvelope = None

# Configure logging to stdout so the Watchdog can capture it
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("EventBroker")


class EventBroker:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        self.host = host
        self.port = port
        self.subscriptions: dict[str, set[asyncio.StreamWriter]] = {}
        # Keep track of which topics each writer is subscribed to for clean cleanup
        self.client_topics: dict[asyncio.StreamWriter, set[str]] = {}
        self.lock = asyncio.Lock()

    async def register_subscription(self, writer: asyncio.StreamWriter, topics: list[str]):
        async with self.lock:
            for topic in topics:
                if topic not in self.subscriptions:
                    self.subscriptions[topic] = set()
                self.subscriptions[topic].add(writer)

                if writer not in self.client_topics:
                    self.client_topics[writer] = set()
                self.client_topics[writer].add(topic)
            logger.info(f"Client registered subscriptions for topics: {topics}")

    async def unregister_subscription(self, writer: asyncio.StreamWriter, topics: list[str]):
        async with self.lock:
            for topic in topics:
                if topic in self.subscriptions and writer in self.subscriptions[topic]:
                    self.subscriptions[topic].remove(writer)
                    if not self.subscriptions[topic]:
                        del self.subscriptions[topic]
                if writer in self.client_topics and topic in self.client_topics[writer]:
                    self.client_topics[writer].remove(topic)
            logger.info(f"Client unregistered subscriptions for topics: {topics}")

    async def remove_client(self, writer: asyncio.StreamWriter):
        async with self.lock:
            topics = self.client_topics.pop(writer, set())
            for topic in topics:
                if topic in self.subscriptions and writer in self.subscriptions[topic]:
                    self.subscriptions[topic].remove(writer)
                    if not self.subscriptions[topic]:
                        del self.subscriptions[topic]
            logger.info("Client connection cleaned up.")

    async def broadcast_event(self, topic: str, data: dict, sender_writer: asyncio.StreamWriter):
        async with self.lock:
            # Combine subscribers to the specific topic and wildcard subscribers
            topic_subs = self.subscriptions.get(topic, set())
            wildcard_subs = self.subscriptions.get("*", set())
            subscribers = list(topic_subs | wildcard_subs)

        if not subscribers:
            logger.debug(f"No subscribers for topic '{topic}'. Event dropped.")
            return

        if EventEnvelope and isinstance(data, dict):
            try:
                envelope = EventEnvelope.validate_payload(topic=topic, data=data)
                data = envelope.data
            except Exception as ve:
                logger.warning(f"Schema validation warning for topic '{topic}': {ve}")

        payload = json.dumps({"topic": topic, "data": data}) + "\n"
        encoded_payload = payload.encode("utf-8")

        dead_writers = []
        for writer in subscribers:
            try:
                writer.write(encoded_payload)
                await writer.drain()
            except Exception as e:
                logger.warning(f"Failed to deliver message to a subscriber on topic '{topic}': {e}")
                dead_writers.append(writer)

        for writer in dead_writers:
            await self.remove_client(writer)

    async def purge_broker(self):
        logger.warning("PANIC RECEIVED: Initiating broker-wide queue purge...")
        async with self.lock:
            payload = json.dumps({"topic": "system", "data": {"action": "purge"}}) + "\n"
            encoded_payload = payload.encode("utf-8")

            # Send the system purge notification to all connected clients
            all_writers = list(self.client_topics.keys())
            for writer in all_writers:
                try:
                    writer.write(encoded_payload)
                    await writer.drain()
                except Exception:
                    pass
            logger.info("Purge notifications sent to all clients.")

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_address = writer.get_extra_info("peername")
        logger.info(f"New client connected from {client_address}")

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break

                try:
                    message = json.loads(line.decode("utf-8").strip())
                except json.JSONDecodeError:
                    logger.error("Received malformed JSON from client.")
                    continue

                action = message.get("action")
                if action == "subscribe":
                    topics = message.get("topics", [])
                    if isinstance(topics, list):
                        await self.register_subscription(writer, topics)
                elif action == "unsubscribe":
                    topics = message.get("topics", [])
                    if isinstance(topics, list):
                        await self.unregister_subscription(writer, topics)
                elif action == "publish":
                    topic = message.get("topic")
                    data = message.get("data", {})
                    if topic:
                        await self.broadcast_event(topic, data, writer)
                elif action == "purge":
                    await self.purge_broker()
                else:
                    logger.warning(f"Unknown action: '{action}'")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error handling client {client_address}: {e}")
        finally:
            logger.info(f"Client disconnected: {client_address}")
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            await self.remove_client(writer)

    async def start(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port, limit=16 * 1024 * 1024)
        addr = server.sockets[0].getsockname()
        logger.info(f"Serving event broker on {addr}")

        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    broker = EventBroker()
    try:
        asyncio.run(broker.start())
    except KeyboardInterrupt:
        logger.info("Broker stopped by KeyboardInterrupt.")
    except Exception as e:
        logger.critical(f"Broker crashed: {e}")
        sys.exit(1)
