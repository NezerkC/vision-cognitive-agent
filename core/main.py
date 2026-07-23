import asyncio
import json
import logging
import os
import signal
import sys
import time

import yaml

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Watchdog: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Watchdog")

class BrainstemWatchdog:
    def __init__(self, use_mock_db: bool = False):
        self.should_run = True
        self.use_mock_db = use_mock_db
        self.processes: dict[str, asyncio.subprocess.Process] = {}
        self.tasks: list[asyncio.Task] = []
        self.process_start_times: dict[str, float] = {}

        # Find absolute paths for the modules relative to this file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        self.project_root = project_root

        # Determine the Python executable to use for child processes.
        # Prefer the local virtualenv python if present.
        venv_python = None
        if sys.platform == "win32":
            candidate = os.path.join(project_root, ".venv", "Scripts", "python.exe")
        else:
            candidate = os.path.join(project_root, ".venv", "bin", "python")

        if os.path.exists(candidate):
            venv_python = candidate
            logger.info(f"Local virtual environment Python detected: {venv_python}")
        else:
            venv_python = sys.executable
            logger.warning(f"No local .venv found. Defaulting to: {venv_python}")
        self.python_executable = venv_python

        # Load startup configuration from config/arranque.yaml if it exists
        arranque_path = os.path.join(project_root, "config", "arranque.yaml")
        modos_mock = {}
        if os.path.exists(arranque_path):
            try:
                with open(arranque_path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg and "modos_mock" in cfg:
                        modos_mock = cfg["modos_mock"]
                logger.info(f"Loaded startup configuration: {modos_mock}")
            except Exception as e:
                logger.error(f"Failed to load config/arranque.yaml: {e}")

        def get_args(service_name: str, yaml_key: str) -> list[str]:
            # CLI --mock flag forces all modes to mock.
            # Otherwise, read from modos_mock (defaulting to True if key doesn't exist).
            is_mock = use_mock_db or modos_mock.get(yaml_key, True)
            return ["--mock"] if is_mock else []

        self.services = {
            "broker": {
                "path": os.path.join(script_dir, "broker_eventos.py"),
                "args": []
            },
            "amigdala": {
                "path": os.path.join(script_dir, "amigdala.py"),
                "args": []
            },
            "router": {
                "path": os.path.join(project_root, "cognitivo", "llm_router.py"),
                "args": []
            },
            "lancedb": {
                "path": os.path.join(project_root, "memoria", "lancedb_manager.py"),
                "args": get_args("lancedb", "lancedb_manager")
            },
            "hipocampo": {
                "path": os.path.join(project_root, "memoria", "hipocampo.py"),
                "args": []
            },
            "vision": {
                "path": os.path.join(project_root, "sentidos", "vision_parietal.py"),
                "args": get_args("vision", "vision_parietal")
            },
            "contexto": {
                "path": os.path.join(project_root, "cognitivo", "contexto_derecho.py"),
                "args": []
            },
            "oido": {
                "path": os.path.join(project_root, "sentidos", "oido_parietal.py"),
                "args": get_args("oido", "oido_parietal")
            },
            "ejecutor": {
                "path": os.path.join(project_root, "cognitivo", "ejecutor_izquierdo.py"),
                "args": get_args("ejecutor", "ejecutor_izquierdo")
            },
            "imaginacion": {
                "path": os.path.join(project_root, "sentidos", "imaginacion_occipital.py"),
                "args": get_args("imaginacion", "imaginacion_occipital")
            },
            "periferico": {
                "path": os.path.join(project_root, "sentidos", "sistema_periferico.py"),
                "args": []
            },
            "intriga": {
                "path": os.path.join(project_root, "cognitivo", "protocolo_intriga.py"),
                "args": get_args("intriga", "protocolo_intriga")
            },
            "web_search": {
                "path": os.path.join(project_root, "cognitivo", "web_search.py"),
                "args": get_args("web_search", "web_search")
            },
            "habla": {
                "path": os.path.join(project_root, "sentidos", "habla_parietal.py"),
                "args": get_args("habla", "habla_parietal")
            }
        }

    async def _log_stream(self, stream, prefix: str):
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                # Ignore invalid characters to prevent encoding crashes on Windows consoles
                decoded_line = line.decode("utf-8", errors="ignore").rstrip()
                logger.info(f"[{prefix}] {decoded_line}")
        except Exception as e:
            logger.error(f"Error reading stream for {prefix}: {e}")

    async def supervise_service(self, name: str, path: str, args: list[str]):
        python_executable = self.python_executable
        backoff_delay = 1
        max_backoff = 30

        while self.should_run:
            logger.info(f"Starting service [{name.upper()}] via: {python_executable} {path} {' '.join(args)}")
            start_time = time.time()
            try:
                proc = await asyncio.create_subprocess_exec(
                    python_executable,
                    path,
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                self.processes[name] = proc
                self.process_start_times[name] = start_time

                # Spawn concurrent log reading tasks
                asyncio.create_task(self._log_stream(proc.stdout, name.upper()))
                asyncio.create_task(self._log_stream(proc.stderr, name.upper() + "-ERR"))

                # Wait for the service process to exit
                exit_code = await proc.wait()
                runtime = time.time() - start_time

                if not self.should_run:
                    logger.info(f"Service [{name.upper()}] stopped intentionally (exit code: {exit_code}).")
                    break

                # Reset backoff if service ran stably for at least 30 seconds
                backoff_delay = 1 if runtime >= 30 else min(backoff_delay * 2, max_backoff)

                logger.error(
                    f"Service [{name.upper()}] exited unexpectedly with code {exit_code} "
                    f"after {int(runtime)}s. Backoff restart in {backoff_delay}s..."
                )
                await asyncio.sleep(backoff_delay)

            except Exception as e:
                logger.critical(f"Supervision failed for service [{name.upper()}]: {e}")
                if self.should_run:
                    backoff_delay = min(backoff_delay * 2, max_backoff)
                    await asyncio.sleep(backoff_delay)
                else:
                    break

    async def write_health_status(self):
        """Write service health status to config/.health_status.json every 3 seconds."""
        health_path = os.path.join(self.project_root, "config", ".health_status.json")
        while self.should_run:
            status = {}
            for name, proc in list(self.processes.items()):
                if proc.returncode is None:
                    uptime = time.time() - self.process_start_times.get(name, time.time())
                    status[name] = {
                        "status": "running",
                        "pid": proc.pid,
                        "uptime_s": int(uptime)
                    }
                else:
                    status[name] = {
                        "status": "stopped",
                        "pid": proc.pid,
                        "exit_code": proc.returncode
                    }
            try:
                os.makedirs(os.path.dirname(health_path), exist_ok=True)
                with open(health_path, "w") as f:
                    json.dump({"services": status, "timestamp": time.time()}, f)
            except Exception as e:
                logger.error(f"Failed to write health status: {e}")
            await asyncio.sleep(3)

    async def start(self):
        # 0. Start the health status writer
        self.tasks.append(
            asyncio.create_task(self.write_health_status())
        )

        # 1. Start the Event Broker first
        broker_cfg = self.services["broker"]
        self.tasks.append(
            asyncio.create_task(
                self.supervise_service("broker", broker_cfg["path"], broker_cfg["args"])
            )
        )

        # 2. Wait for the Event Broker to initialize and bind the TCP port
        logger.info("Initializing heartbeat socket connection pool...")
        await asyncio.sleep(1.5)

        # 3. Start the remaining services concurrently
        for name, cfg in self.services.items():
            if name == "broker":
                continue
            self.tasks.append(
                asyncio.create_task(
                    self.supervise_service(name, cfg["path"], cfg["args"])
                )
            )

        # Keep running until cancelled
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            logger.info("Watchdog gather cancelled.")

    def stop(self):
        logger.info("Initiating shutdown of all supervised services...")
        self.should_run = False

        # Cancel all supervise tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Terminate all subprocesses
        for name, proc in list(self.processes.items()):
            try:
                proc.terminate()
                logger.info(f"Sent terminate signal to [{name.upper()}] process.")
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"Failed to terminate [{name.upper()}]: {e}")

async def main():
    use_mock = "--mock" in sys.argv
    if use_mock:
        logger.info("Mock mode enabled for LanceDB manager.")

    watchdog = BrainstemWatchdog(use_mock_db=use_mock)

    # Register OS signal handlers
    loop = asyncio.get_running_loop()

    def handle_shutdown():
        watchdog.stop()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_shutdown)

    try:
        await watchdog.start()
    except KeyboardInterrupt:
        logger.info("Watchdog interrupted by user.")
    finally:
        watchdog.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Watchdog main thread terminated.")
