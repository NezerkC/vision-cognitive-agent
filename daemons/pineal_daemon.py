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
        idle_threshold_seconds: float = 10.0,
        is_mock: bool = False,
    ):
        self.host = host
        self.port = port
        self.idle_threshold = idle_threshold_seconds
        self.is_mock = is_mock
        self.last_activity_timestamp = time.time()
        self.is_sleeping = False

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

    async def run_consolidation(self) -> dict[str, Any]:
        """
        Consolidates short-term memory: transfers items between Hot (SSD/RAM) and Cold (HDD)
        tier based on W weight and age decay.
        """
        logger.info("🧠 Executing short-term memory consolidation...")
        consolidated_count = 0
        try:
            if self.db_manager.table is not None:
                # Scan hot table rows
                df = self.db_manager.table.to_pandas()
                for _, row in df.iterrows():
                    cw = float(row.get("coordenada_w", 100.0))
                    # Items with low W decay move to Cold tier
                    if cw < 50.0 and self.db_manager.cold_table is not None:
                        row_dict = {
                            "vector": list(row.get("vector", [])),
                            "text": row.get("text", ""),
                            "coordenada_x": float(row.get("coordenada_x", 0.0)),
                            "coordenada_y": float(row.get("coordenada_y", 0.0)),
                            "coordenada_z": float(row.get("coordenada_z", 0.0)),
                            "coordenada_w": cw,
                            "escala_magnitud": str(row.get("escala_magnitud", "KB")),
                            "metadata": str(row.get("metadata", "{}")),
                        }
                        self.db_manager.cold_table.add([row_dict])
                        consolidated_count += 1
        except Exception as e:
            logger.error(f"Error during memory consolidation: {e}")

        logger.info(f"Memory consolidation complete: {consolidated_count} items migrated to Cold Tier.")
        return {"status": "success", "consolidated_items": consolidated_count}

    async def generate_context_summary(self) -> str:
        """
        Generates a summary of daily context and persists it to hot memory.
        """
        logger.info("📝 Generating context summary during sleep cycle...")
        summary_text = (
            f"Consolidación nocturna ({time.strftime('%Y-%m-%d %H:%M:%S')}): "
            f"Vigilia finalizada sin anomalías críticas. Estado del sistema nominal."
        )
        try:
            await self.cerebelo.guardar_recuerdo(
                texto=summary_text,
                coordenada_x=0.0,
                coordenada_y=0.0,
                coordenada_z=0.0,
                coordenada_w=95.0,  # High W for summaries
                metadata={"tipo": "resumen_diario", "generador": "pineal_daemon"},
            )
        except Exception as e:
            logger.error(f"Error persisting context summary: {e}")

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

                subscribe_msg = json.dumps({
                    "action": "subscribe",
                    "topics": [
                        "canal.sistema.contexto_actual",
                        "canal.sensorial.audio.transcripcion",
                        "canal.sensorial.vision",
                        "canal.cognitivo.entrada",
                        "system",
                    ],
                }) + "\n"
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

                        if topic in [
                            "canal.sistema.contexto_actual",
                            "canal.sensorial.audio.transcripcion",
                            "canal.sensorial.vision",
                            "canal.cognitivo.entrada",
                        ]:
                            self.register_activity()

                        if topic == "system" and data.get("action") == "force_sleep":
                            await self.trigger_sleep_cycle(writer)

                    except asyncio.TimeoutError:
                        # Check idle threshold
                        elapsed_idle = time.time() - self.last_activity_timestamp
                        if elapsed_idle >= self.idle_threshold and not self.is_sleeping:
                            await self.trigger_sleep_cycle(writer)

            except Exception as e:
                logger.error(f"PinealDaemon error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)


if __name__ == "__main__":
    mock_flag = "--mock" in sys.argv
    daemon = PinealDaemon(is_mock=mock_flag, idle_threshold_seconds=5.0)
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("PinealDaemon stopped.")
