import asyncio
import json
import logging
import os
import signal
import sys
import time
from collections.abc import Mapping, MutableMapping

from dotenv import dotenv_values

# Relayed service output (progress bars, emojis) may not fit the console codec (cp1252 on Windows).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Watchdog: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Watchdog")


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_project_env(
    project_root: str,
    environ: MutableMapping[str, str] | None = None,
    dotenv_path: str | os.PathLike | None = None,
) -> None:
    """Load the project .env into `environ` (default: this process) without overriding variables already set."""
    environ = os.environ if environ is None else environ
    dotenv_path = dotenv_path or os.path.join(project_root, ".env")
    if os.path.exists(dotenv_path):
        for key, value in dotenv_values(dotenv_path).items():
            if value is not None:
                environ.setdefault(key, value)


def build_child_env(
    project_root: str,
    base_env: Mapping[str, str] | None = None,
    dotenv_path: str | os.PathLike | None = None,
) -> dict[str, str]:
    """Environment for supervised services.

    - Project packages (core, cognitivo, sentidos, memoria) importable from any service script.
    - Values from the project .env loaded, without overriding variables already set in the shell.
    - UTF-8 stdio: services write to pipes, which default to the locale codec (cp1252 on Windows).
    """
    env = dict(os.environ if base_env is None else base_env)
    load_project_env(project_root, env, dotenv_path)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (project_root, env.get("PYTHONPATH")) if p)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


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

        # Startup switches from config/arranque.yaml; unlisted services run for real.
        # core/main.py also runs as a script, so make the project importable first.
        if PROJECT_ROOT not in sys.path:
            sys.path.insert(0, PROJECT_ROOT)
        from core.arranque import is_mock, load_modos_mock

        modos_mock = load_modos_mock(project_root)
        logger.info(f"Loaded startup configuration: {modos_mock}")

        def get_args(service_name: str, yaml_key: str) -> list[str]:
            # The --mock CLI flag forces every service into mock mode.
            return ["--mock"] if is_mock(modos_mock, yaml_key, force=use_mock_db) else []

        self.services = {
            "broker": {"path": os.path.join(script_dir, "broker_eventos.py"), "args": []},
            "amigdala": {"path": os.path.join(script_dir, "amigdala.py"), "args": []},
            "router": {"path": os.path.join(project_root, "cognitivo", "llm_router.py"), "args": []},
            "lancedb": {
                "path": os.path.join(project_root, "memoria", "lancedb_manager.py"),
                "args": get_args("lancedb", "lancedb_manager"),
            },
            "hipocampo": {"path": os.path.join(project_root, "memoria", "hipocampo.py"), "args": []},
            "vision": {
                "path": os.path.join(project_root, "sentidos", "vision_parietal.py"),
                "args": get_args("vision", "vision_parietal"),
            },
            "contexto": {"path": os.path.join(project_root, "cognitivo", "contexto_derecho.py"), "args": []},
            "oido": {
                "path": os.path.join(project_root, "sentidos", "oido_parietal.py"),
                "args": get_args("oido", "oido_parietal"),
            },
            "ejecutor": {
                "path": os.path.join(project_root, "cognitivo", "ejecutor_izquierdo.py"),
                "args": get_args("ejecutor", "ejecutor_izquierdo"),
            },
            "imaginacion": {
                "path": os.path.join(project_root, "sentidos", "imaginacion_occipital.py"),
                "args": get_args("imaginacion", "imaginacion_occipital"),
            },
            "periferico": {"path": os.path.join(project_root, "sentidos", "sistema_periferico.py"), "args": []},
            "intriga": {
                "path": os.path.join(project_root, "cognitivo", "protocolo_intriga.py"),
                "args": get_args("intriga", "protocolo_intriga"),
            },
            "web_search": {
                "path": os.path.join(project_root, "cognitivo", "web_search.py"),
                "args": get_args("web_search", "web_search"),
            },
            "habla": {
                "path": os.path.join(project_root, "sentidos", "habla_parietal.py"),
                "args": get_args("habla", "habla_parietal"),
            },
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

    async def _spawn(self, path: str, args: list[str]) -> asyncio.subprocess.Process:
        # Run from the project root (relative data paths) with a fresh env, so .env edits apply on restart.
        return await asyncio.create_subprocess_exec(
            self.python_executable,
            path,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.project_root,
            env=build_child_env(self.project_root),
        )

    async def supervise_service(self, name: str, path: str, args: list[str]):
        python_executable = self.python_executable
        backoff_delay = 1
        max_backoff = 30

        while self.should_run:
            logger.info(f"Starting service [{name.upper()}] via: {python_executable} {path} {' '.join(args)}")
            start_time = time.time()
            try:
                proc = await self._spawn(path, args)
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
                    status[name] = {"status": "running", "pid": proc.pid, "uptime_s": int(uptime)}
                else:
                    status[name] = {"status": "stopped", "pid": proc.pid, "exit_code": proc.returncode}
            try:
                os.makedirs(os.path.dirname(health_path), exist_ok=True)
                with open(health_path, "w") as f:
                    json.dump({"services": status, "timestamp": time.time()}, f)
            except Exception as e:
                logger.error(f"Failed to write health status: {e}")
            await asyncio.sleep(3)

    async def start(self):
        # 0. Start the health status writer
        self.tasks.append(asyncio.create_task(self.write_health_status()))

        # 1. Start the Event Broker first
        broker_cfg = self.services["broker"]
        self.tasks.append(asyncio.create_task(self.supervise_service("broker", broker_cfg["path"], broker_cfg["args"])))

        # 2. Wait for the Event Broker to initialize and bind the TCP port
        logger.info("Initializing heartbeat socket connection pool...")
        await asyncio.sleep(1.5)

        # 3. Start the remaining services concurrently
        for name, cfg in self.services.items():
            if name == "broker":
                continue
            self.tasks.append(asyncio.create_task(self.supervise_service(name, cfg["path"], cfg["args"])))

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
    use_multi_process = "--multi-process" in sys.argv

    if use_multi_process:
        logger.info("Modo multi-proceso seleccionado (--multi-process).")
        if use_mock:
            logger.info("Mock mode enabled for LanceDB manager.")
        watchdog = BrainstemWatchdog(use_mock_db=use_mock)

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
    else:
        # Default: Unified In-Process Hexagonal Orchestrator. Everything runs in this process, so give it what
        # the watchdog gives its children: project packages importable, relative data paths anchored at the
        # project root, and .env loaded.
        if PROJECT_ROOT not in sys.path:
            sys.path.insert(0, PROJECT_ROOT)
        os.chdir(PROJECT_ROOT)
        load_project_env(PROJECT_ROOT)

        from core.orchestrator import BrainstemOrchestrator

        logger.info("Ejecutando Orquestador Cerebral Unificado (Clean/Hexagonal in-memory mode)...")
        orchestrator = BrainstemOrchestrator(use_mock=use_mock)
        try:
            await orchestrator.start()
        except KeyboardInterrupt:
            logger.info("Orquestador interrumpido por el usuario.")
        finally:
            await orchestrator.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Watchdog main thread terminated.")
