"""
Unified Brainstem Orchestrator for Visión OS (Clean Hexagonal Architecture).
Runs all neural services inside a single supervised asyncio runtime using the
high-performance AsyncInMemoryEventBus and a backward-compatible TCP socket bridge.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Any

from cognitivo.contexto_derecho import ContextoDerecho
from cognitivo.ejecutor_izquierdo import EjecutorIzquierdo

# Service Imports
from cognitivo.llm_router import LLMRouter
from cognitivo.protocolo_intriga import ProtocoloIntriga
from core.adapters.event_bus_inmemory import AsyncInMemoryEventBus
from core.adapters.event_bus_tcp_bridge import TCPEventBusBridge
from core.amigdala import Amigdala
from core.arranque import is_mock, load_modos_mock
from daemons.pineal_daemon import PinealDaemon
from memoria.lancedb_manager import LanceDBManager
from sentidos.habla_parietal import HablaParietal
from sentidos.imaginacion_occipital import ImaginacionOccipital
from sentidos.oido_parietal import OidoParietal
from sentidos.vision_parietal import VisionParietal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] BrainstemOrchestrator: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("BrainstemOrchestrator")

ServiceFactory = Callable[[], Awaitable[None]]
RESTART_DELAY_SECONDS = 3
HEALTH_INTERVAL_SECONDS = 3


class BrainstemOrchestrator:
    """
    Master In-Process Orchestrator for Visión OS.
    Runs all cognitive daemons concurrently on top of the in-memory event bus
    with an optional TCP bridge for external clients.
    """

    def __init__(self, use_mock: bool = False, enable_tcp_bridge: bool = True, tcp_port: int = 5000):
        self.use_mock = use_mock
        self.enable_tcp_bridge = enable_tcp_bridge
        self.tcp_port = tcp_port
        self.event_bus = AsyncInMemoryEventBus()
        self.tcp_bridge: TCPEventBusBridge | None = None
        self.tasks: list[asyncio.Task] = []
        self.should_run = True
        # name -> {"status", "started_at", "restarts", "last_error"}; published for GET /api/health.
        self.service_status: dict[str, dict[str, Any]] = {}

        # Project directory resolution
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(script_dir)

        # Load startup settings
        self.modos_mock: dict[str, bool] = load_modos_mock(self.project_root)
        logger.info(f"Loaded startup configuration: {self.modos_mock}")

    def is_service_mock(self, service_key: str) -> bool:
        """Mock only when --mock is set or the service is explicitly flagged in config/arranque.yaml."""
        return is_mock(self.modos_mock, service_key, force=self.use_mock)

    async def start(self) -> None:
        """
        Launches all neural services and bridges inside the single asyncio event loop.
        """
        logger.info("============================================================")
        logger.info("🧠 Visión OS — Iniciando Orquestador Cerebral Unificado")
        logger.info("============================================================")

        # 1. Start TCP Bridge on port 5000 for external/legacy tools
        if self.enable_tcp_bridge:
            self.tcp_bridge = TCPEventBusBridge(self.event_bus, host="127.0.0.1", port=self.tcp_port)
            await self.tcp_bridge.start()
            logger.info(f"✅ Bridge TCP activo en 127.0.0.1:{self.tcp_port}")

        # 2. Wire In-Memory Service: Amígdala
        amigdala = Amigdala(host="127.0.0.1", port=self.tcp_port)

        async def amigdala_input_handler(topic: str, data: dict[str, Any]):
            await amigdala.handle_cognitive_input(data, self.event_bus.publish)

        async def amigdala_panic_handler(topic: str, data: dict[str, Any]):
            await amigdala.trigger_panic_purge(event_bus=self.event_bus)

        await self.event_bus.subscribe(["canal.cognitivo.entrada"], amigdala_input_handler)
        await self.event_bus.subscribe(["canal.seguridad.panic"], amigdala_panic_handler)
        logger.info("🛡️ Amígdala (Perímetro de Seguridad) enlazada en memoria.")

        # 3. Wire In-Memory Service: LanceDB Memory Manager
        lancedb_mock = self.is_service_mock("lancedb_manager")
        lancedb_mgr = LanceDBManager(host="127.0.0.1", port=self.tcp_port)
        lancedb_mgr.init_db(mock_embedder=lancedb_mock)

        # 4. Run every service under supervision
        for name, factory in self.service_factories(lancedb_mgr, lancedb_mock):
            task = asyncio.create_task(self._supervise(name, factory), name=f"Task_{name}")
            self.tasks.append(task)
        self.tasks.append(asyncio.create_task(self.write_health_status(), name="Task_Health"))

        logger.info(f"✨ Todos los {len(self.tasks)} módulos neurales se ejecutan en un solo runtime Python.")

        # Keep running until cancelled
        try:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info("BrainstemOrchestrator cancellation requested.")
        finally:
            await self.stop()

    def service_factories(self, lancedb_mgr, lancedb_mock: bool) -> list[tuple[str, ServiceFactory]]:
        """(name, factory) pairs. Each factory builds a fresh service coroutine, so a crashed service can be
        restarted (a coroutine object can only be awaited once). Nothing is created until a factory is called."""
        port = self.tcp_port
        mock = self.is_service_mock

        def gateway() -> Awaitable[None]:
            # FastAPI gateway on 127.0.0.1:8000 (web HUD, Vision Studio API and WebSocket).
            from sentidos.sistema_periferico import run_server

            return run_server()

        return [
            ("Router Frontal", lambda: LLMRouter(port=port).run()),
            ("LanceDB Daemon", lambda: lancedb_mgr.run()),
            ("Visión Parietal", lambda: VisionParietal(port=port, force_mock=mock("vision_parietal")).run()),
            ("Oído Parietal", lambda: OidoParietal(port=port, force_mock=mock("oido_parietal")).run()),
            ("Habla Parietal", lambda: HablaParietal(port=port, force_mock=mock("habla_parietal")).run()),
            ("Contexto Derecho", lambda: ContextoDerecho(port=port).run()),
            ("Protocolo Intriga", lambda: ProtocoloIntriga(port=port).run()),
            ("Ejecutor Izquierdo", lambda: EjecutorIzquierdo(port=port, is_mock=mock("ejecutor_izquierdo")).run()),
            (
                "Imaginación Occipital",
                lambda: ImaginacionOccipital(port=port, force_mock=mock("imaginacion_occipital")).run(),
            ),
            ("Pineal Daemon", lambda: PinealDaemon(port=port, is_mock=lancedb_mock).run()),
            ("Sistema Periférico", gateway),
        ]

    async def _supervise(self, name: str, factory: ServiceFactory) -> None:
        """Runs a service, restarting it with a fresh coroutine after it crashes or exits."""
        status = self.service_status.setdefault(name, {"restarts": 0, "last_error": None})
        while self.should_run:
            status.update(status="running", started_at=time.time())
            try:
                logger.info(f"[{name.upper()}] Iniciando servicio...")
                await factory()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{name.upper()}] Error en ejecución: {e}", exc_info=True)
                status["last_error"] = str(e)
            if self.should_run:
                status["restarts"] += 1
                status["status"] = "restarting"
                logger.warning(f"[{name.upper()}] Servicio detenido. Reiniciando en {RESTART_DELAY_SECONDS}s...")
                await asyncio.sleep(RESTART_DELAY_SECONDS)
        status["status"] = "stopped"

    def health_snapshot(self) -> dict[str, Any]:
        """Per-service status in the same shape the multi-process watchdog writes."""
        now = time.time()
        services = {
            name: {
                "status": status.get("status", "starting"),
                "uptime_s": int(now - status["started_at"]) if status.get("started_at") else 0,
                "restarts": status.get("restarts", 0),
                "last_error": status.get("last_error"),
            }
            for name, status in self.service_status.items()
        }
        return {"services": services, "timestamp": now}

    def write_health_file(self) -> None:
        """Writes config/.health_status.json, which GET /api/health reads."""
        health_path = os.path.join(self.project_root, "config", ".health_status.json")
        os.makedirs(os.path.dirname(health_path), exist_ok=True)
        with open(health_path, "w", encoding="utf-8") as f:
            json.dump(self.health_snapshot(), f)

    async def write_health_status(self) -> None:
        """Refreshes the health file every HEALTH_INTERVAL_SECONDS while the orchestrator runs."""
        while self.should_run:
            try:
                self.write_health_file()
            except OSError as e:
                logger.error(f"No se pudo escribir el estado de salud: {e}")
            await asyncio.sleep(HEALTH_INTERVAL_SECONDS)

    async def stop(self) -> None:
        """Gracefully shuts down the orchestrator and all managed tasks."""
        if not self.should_run:
            return
        logger.info("🛑 Deteniendo Orquestador Cerebral Unificado...")
        self.should_run = False

        for task in self.tasks:
            if not task.done():
                task.cancel()

        if self.tcp_bridge:
            await self.tcp_bridge.stop()

        await self.event_bus.shutdown()
        logger.info("👋 Visión OS detenido limpiamente.")


async def main():
    use_mock = "--mock" in sys.argv
    orchestrator = BrainstemOrchestrator(use_mock=use_mock)

    loop = asyncio.get_running_loop()

    def handle_signal():
        asyncio.create_task(orchestrator.stop())

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)

    try:
        await orchestrator.start()
    except KeyboardInterrupt:
        logger.info("Interrupción de teclado detectada.")
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
