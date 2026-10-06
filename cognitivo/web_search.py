"""
Web Search Daemon for Visión OS.

Connects to the Event Broker and listens on `canal.web.busqueda` for
search requests. Performs the search using the WebSearchEngine (with
automatic fallback DuckDuckGo → Tavily → error) and publishes results
to `canal.web.resultado`.

This daemon is OPTIONAL — the web search skill also works when called
directly from the LangGraph (nodo_web). The daemon exists so non-graph
modules (Amígdala, Ejecutor, etc.) can search via the broker.
"""

import asyncio
import json
import logging
import os
import sys
import time

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cognitivo.skills.websearch_tool import WebSearchEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] WebSearchDaemon: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("WebSearchDaemon")


class WebSearchDaemon:
    """Event Broker daemon that handles web search requests."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5000, is_mock: bool = False):
        self.host = host
        self.port = port
        self.is_mock = is_mock
        self.engine = WebSearchEngine()

    async def handle_search_request(self, data: dict, writer):
        """Process a search request from the broker and publish results."""
        request_id = data.get("request_id", f"web-{int(time.time())}")
        query = data.get("query", "")
        max_results = min(int(data.get("max_results", 5)), 10)

        logger.info(f"Search request [{request_id}]: '{query}' (max: {max_results})")

        if not query or not query.strip():
            result = {
                "request_id": request_id,
                "status": "error",
                "source": "mock",
                "results": [],
                "error": "Empty query",
                "timestamp": time.time(),
            }
        elif self.is_mock:
            result = {
                "request_id": request_id,
                "status": "success",
                "source": "mock",
                "results": [
                    {
                        "title": f"Resultado simulado para: {query}",
                        "url": "",
                        "snippet": "This is a mock search result for development/testing.",
                    }
                ],
                "error": None,
                "timestamp": time.time(),
            }
        else:
            try:
                response = await self.engine.buscar(query, max_results)
                result = {
                    "request_id": request_id,
                    "status": response.status,
                    "source": response.source,
                    "results": [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in response.results],
                    "error": response.error,
                    "timestamp": time.time(),
                }
            except Exception as e:
                logger.error(f"Search error [{request_id}]: {e}")
                result = {
                    "request_id": request_id,
                    "status": "error",
                    "source": "mock",
                    "results": [],
                    "error": str(e),
                    "timestamp": time.time(),
                }

        # Publish result to canal.web.resultado
        payload = {
            "action": "publish",
            "topic": "canal.web.resultado",
            "data": result,
        }
        try:
            writer.write((json.dumps(payload) + "\n").encode("utf-8"))
            await writer.drain()
            logger.info(f"Published {len(result.get('results', []))} results for [{request_id}]")
        except Exception as e:
            logger.error(f"Failed to publish search result: {e}")

    async def run(self):
        """Main loop: connect to broker and handle events."""
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                subscribe_msg = (
                    json.dumps(
                        {
                            "action": "subscribe",
                            "topics": ["canal.web.busqueda", "system"],
                        }
                    )
                    + "\n"
                )
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                while True:
                    line = await reader.readline()
                    if not line:
                        break

                    event = json.loads(line.decode("utf-8").strip())
                    topic = event.get("topic")
                    data = event.get("data", {})

                    if topic == "canal.web.busqueda":
                        asyncio.create_task(self.handle_search_request(data, writer))

                    elif topic == "system":
                        action = data.get("action") or data.get("command")
                        if action == "shutdown":
                            logger.info("Shutdown command received. Exiting.")
                            return
                        elif action == "purge":
                            logger.info("Purge signal received. Resetting engine state.")
                            self.engine = WebSearchEngine()

            except Exception as e:
                logger.error(f"Connection error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)


if __name__ == "__main__":
    mock_flag = "--mock" in sys.argv
    daemon = WebSearchDaemon(is_mock=mock_flag)
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("WebSearchDaemon stopped.")
