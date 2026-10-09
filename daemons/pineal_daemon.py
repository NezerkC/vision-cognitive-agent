"""
Pineal Gland Daemon (Ciclo Vigilia / Sueño) for Visión OS.

Handles asynchronous system background routines during idle / sleep periods:
1. Context summary generation (daily activity summary).
2. Short-term memory consolidation (Hot/Cold storage tiering migrations based on W factor / decay).
3. Nocturnal GraphRAG relational graph indexing across vector memories.
"""

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cognitivo.memoria import CerebeloMemoria4D
from memoria.lancedb_manager import LanceDBManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] PinealDaemon: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("PinealDaemon")

# Hot rows whose emotional gravity W decays below this move to the cold tier.
COLD_W_THRESHOLD = 50.0
MAX_ACTIVITY_LINES = 200
MAX_ACTIVITY_CHARS = 300
# Events the daily summary is built from: screen context, voice, requests, external webhooks and uploads.
ACTIVITY_TOPICS = [
    "canal.sistema.contexto_actual",
    "canal.sensorial.audio.transcripcion",
    "canal.sensorial.vision",
    "canal.cognitivo.entrada",
    "canal.sensorial.periferico",
    "canal.sensorial.archivo_recibido",
]


async def _resumir_con_llm(prompt: str) -> str:
    from cognitivo.llm_router import enrutar_peticion

    return await enrutar_peticion(prompt, esfuerzo="esfuerzo_bajo")


class PinealDaemon:
    """
    Pineal Gland Daemon orchestrating the agent's wake/sleep cycle.
    Automatically triggers memory consolidation, context summarization,
    and nocturnal GraphRAG indexing when system is idle.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        idle_threshold_seconds: float = 600.0,
        is_mock: bool = False,
        summarizer: Callable[[str], Awaitable[str]] | None = None,
    ):
        self.host = host
        self.port = port
        # Sleep needs a real idle period: each cycle summarizes the activity with an LLM call.
        self.idle_threshold = idle_threshold_seconds
        self.is_mock = is_mock
        self.last_activity_timestamp = time.time()
        self.is_sleeping = False
        self.summarizer = summarizer or _resumir_con_llm
        # What happened since the last summary, as short text lines (screens, voice, requests).
        self.activity_log: list[str] = []

        self.db_manager = LanceDBManager()
        self.cerebelo = CerebeloMemoria4D(db_manager=self.db_manager)

        # GraphRAG memory store: simple relational map of memory node triples
        self.graph_rag_triples: list[dict[str, str]] = []

    def register_activity(self):
        """Resets idle timer when sensory or user activity is detected."""
        self.last_activity_timestamp = time.time()
        if self.is_sleeping:
            self.is_sleeping = False
            logger.info("🌅 WAKE CYCLE TRIGGERED: System activity detected. Exiting sleep state.")

    def record_activity(self, topic: str, data: dict) -> None:
        """Note what happened (screen context, voice, requests) for the next summary and reset the idle timer."""
        self.register_activity()
        text = None
        if topic == "canal.sistema.contexto_actual":
            text = f"Pantalla: {data.get('contexto', '')}"
        elif topic == "canal.sensorial.audio.transcripcion":
            text = f"Voz: {data.get('transcripcion', '')}"
        elif topic == "canal.cognitivo.entrada":
            text = f"Petición: {data.get('prompt', '')}"
        elif topic == "canal.sensorial.periferico":
            text = f"Webhook externo: {json.dumps(data, ensure_ascii=False)}"
        elif topic == "canal.sensorial.archivo_recibido":
            text = f"Archivo recibido: {data.get('nombre', '')}"
        if text and text.split(": ", 1)[1].strip():
            self.activity_log.append(text[:MAX_ACTIVITY_CHARS])
            del self.activity_log[:-MAX_ACTIVITY_LINES]

    async def run_consolidation(self) -> dict[str, Any]:
        """
        Moves hot rows whose W decayed below COLD_W_THRESHOLD to the cold tier: copied, then deleted from hot.

        Rows without an id are matched by the same W filter on delete; a low-W row stored between the copy and
        the delete would be removed without a copy, which is acceptable because new rows below the hot routing
        threshold (70) go straight to the cold tier.
        """
        logger.info("🧠 Executing short-term memory consolidation...")
        hot, cold = self.db_manager.table, self.db_manager.cold_table
        if hot is None or cold is None:
            return {"status": "error", "consolidated_items": 0, "detail": "Memory tiers not initialized."}
        try:
            rows = hot.to_arrow().to_pylist()
            decayed = [r for r in rows if float(r.get("coordenada_w") or 0.0) < COLD_W_THRESHOLD]
            if decayed:
                cold.add(decayed)
                hot.delete(f"coordenada_w < {COLD_W_THRESHOLD}")
        except Exception as e:
            logger.error(f"Error during memory consolidation: {e}")
            return {"status": "error", "consolidated_items": 0, "detail": str(e)}

        logger.info(f"Memory consolidation complete: {len(decayed)} items moved to the cold tier.")
        return {"status": "success", "consolidated_items": len(decayed)}

    async def generate_context_summary(self) -> str | None:
        """
        Summarizes the activity recorded since the last summary with the LLM and stores it in hot memory.
        Returns None, storing nothing, when there was no activity or the LLM failed (the activity is kept).
        """
        if not self.activity_log:
            logger.info("📝 No activity since the last summary; nothing to consolidate.")
            return None
        logger.info(f"📝 Summarizing {len(self.activity_log)} activity entries during the sleep cycle...")
        prompt = (
            "Resume en 3 a 6 frases lo que hizo el usuario y lo que ocurrió en el sistema durante este periodo, "
            "para guardarlo como memoria de largo plazo. Usa solo estos registros, sin inventar nada:\n\n"
            + "\n".join(f"- {line}" for line in self.activity_log)
        )
        try:
            summary_text = (await self.summarizer(prompt)).strip()
        except Exception as e:
            logger.error(f"Could not summarize the activity: {e}. Keeping it for the next cycle.")
            return None
        if not summary_text:
            return None

        await self.cerebelo.guardar_recuerdo(
            texto=summary_text,
            coordenada_x=0.0,
            coordenada_y=0.0,
            coordenada_z=0.0,
            coordenada_w=95.0,  # High W for summaries
            metadata={"tipo": "resumen_diario", "generador": "pineal_daemon", "entradas": len(self.activity_log)},
        )
        self.activity_log.clear()
        return summary_text

    async def build_graphrag_index(self) -> list[dict[str, str]]:
        """
        Executes nocturnal GraphRAG indexing, creating subject-predicate-object
        relations between memory concepts.
        """
        logger.info("🕸️ Constructing nocturnal GraphRAG relational graph...")
        new_triples = []
        try:
            results = await self.cerebelo.buscar_hibrida_rrf(query="sistema memoria", top_n=5)
            for i in range(len(results) - 1):
                triple = {
                    "subject": str(results[i].get("text", "")[:30]),
                    "predicate": "relacionado_con",
                    "object": str(results[i + 1].get("text", "")[:30]),
                }
                new_triples.append(triple)
                self.graph_rag_triples.append(triple)
        except Exception as e:
            logger.error(f"Error building GraphRAG index: {e}")

        logger.info(f"GraphRAG indexing complete: {len(new_triples)} new triples indexed.")
        return new_triples

    async def trigger_sleep_cycle(self, writer=None):
        """Executes full sleep cycle routines: consolidation, summary, and GraphRAG."""
        if self.is_sleeping:
            return
        self.is_sleeping = True
        logger.info("🌙 SLEEP CYCLE ACTIVATED: System is idle. Starting Pineal routines...")

        # 1. Consolidate memories
        await self.run_consolidation()

        # 2. Generate daily context summary
        summary = await self.generate_context_summary()

        # 3. Build GraphRAG graph index
        triples = await self.build_graphrag_index()

        # Publish notification onto broker if writer exists
        if writer:
            event_data = {
                "action": "publish",
                "topic": "canal.sistema.anuncios",
                "data": {
                    "mensaje": f"🌙 Ciclo de Sueño Pineal completado. {len(triples)} nodos GraphRAG indexados.",
                    "resumen": summary,
                    "timestamp": time.time(),
                },
            }
            try:
                writer.write((json.dumps(event_data) + "\n").encode("utf-8"))
                await writer.drain()
            except Exception as e:
                logger.error(f"Failed to publish pineal sleep notification: {e}")

    async def run(self):
        """Main event loop monitoring idle state and broker messages."""
        self.cerebelo.init_memory(mock_embedder=self.is_mock)

        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                subscribe_msg = (
                    json.dumps(
                        {
                            "action": "subscribe",
                            "topics": [*ACTIVITY_TOPICS, "system"],
                        }
                    )
                    + "\n"
                )
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                while True:
                    # Non-blocking read with timeout to check idle timer
                    try:
                        line = await asyncio.wait_for(reader.readline(), timeout=2.0)
                        if not line:
                            break
                        event = json.loads(line.decode("utf-8").strip())
                        topic = event.get("topic")
                        data = event.get("data", {})

                        if topic in ACTIVITY_TOPICS:
                            self.record_activity(topic, data)

                        if topic == "system" and data.get("action") == "force_sleep":
                            await self.trigger_sleep_cycle(writer)

                    except TimeoutError:
                        # Check idle threshold
                        elapsed_idle = time.time() - self.last_activity_timestamp
                        if elapsed_idle >= self.idle_threshold and not self.is_sleeping:
                            await self.trigger_sleep_cycle(writer)

            except Exception as e:
                logger.error(f"PinealDaemon error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)


if __name__ == "__main__":
    mock_flag = "--mock" in sys.argv
    daemon = PinealDaemon(is_mock=mock_flag)
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("PinealDaemon stopped.")
