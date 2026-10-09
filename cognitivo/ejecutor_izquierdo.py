import asyncio
import json
import logging
import os
import signal
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] HemisferioIzquierdo: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("EjecutorIzquierdo")

# Attempt to load pyautogui safely (on a headless Linux it raises display errors, not only ImportError)
pyautogui = None
PYAUTOGUI_ERROR = ""
try:
    import pyautogui
except Exception as e:
    PYAUTOGUI_ERROR = str(e) or type(e).__name__
    logger.warning(f"pyautogui unavailable ({e}). UI actions will be reported as not executed.")

# Keyboard/mouse commands execute_control_ui understands, besides "escribir:<text>".
UI_COMMANDS = {"win", "enter", "click"}

ACTION_TOPIC = "canal.ejecucion.accion"
APPROVAL_TOPIC = "canal.ejecucion.aprobacion"
RESULT_TOPIC = "canal.ejecucion.resultado"
SUPPORTED_TOOLS = frozenset({"control_ui", "ejecutar_script"})
# A request the human has not answered within this window can no longer be approved.
PENDING_TTL_SECONDS = 300
# Approved shell commands are killed (with everything they spawned) after this long.
SCRIPT_TIMEOUT_SECONDS = 60


async def _kill_process_tree(process: asyncio.subprocess.Process) -> None:
    """Kill a shell and its children: killing only the shell leaves the spawned command running."""
    if process.returncode is not None:
        return
    try:
        if sys.platform == "win32":
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/PID",
                str(process.pid),
                "/T",
                "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, OSError) as e:
        logger.warning(f"Could not kill process tree {process.pid}: {e}")
    await process.wait()


class EjecutorIzquierdo:
    """Runs keyboard/mouse and shell actions, only after a human approves each one (HITL).

    canal.ejecucion.accion registers a pending request (the GUI shows it as a ticket);
    canal.ejecucion.aprobacion {"request_id", "approved": true|false} runs or discards it.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5000, is_mock: bool = False, clock=time.monotonic):
        self.host = host
        self.port = port
        self.is_mock = is_mock
        # Without pyautogui (e.g. a headless host) UI actions fail with an explicit error; shell commands still run.
        self.ui_available = pyautogui is not None
        self._clock = clock
        self.pending: dict[str, tuple[dict, float]] = {}

    async def execute_control_ui(self, commands) -> dict:
        """
        Executes pyautogui keyboard/mouse simulation.
        Visual warning console log printed in red/orange.
        """
        # Red/Orange safety alert
        print(
            "\033[93m"
            + "=" * 80
            + "\n[ALERTA DE SEGURIDAD] HEMISFERIO IZQUIERDO TOMANDO CONTROL DEL SISTEMA"
            + "\033[0m"
        )
        print(f"\033[91mComandos UI recibidos: {commands}\033[0m")
        print("\033[93m" + "=" * 80 + "\033[0m")

        if self.is_mock:
            logger.info("[MOCK MODE] UI actions not executed.")
            return {
                "status": "error",
                "detail": "Not executed: ejecutor_izquierdo runs in mock mode (config/arranque.yaml).",
            }
        if not self.ui_available:
            return {"status": "error", "detail": f"Not executed: UI automation needs pyautogui ({PYAUTOGUI_ERROR})."}

        commands = [cmd.strip() for cmd in commands]
        unknown = [cmd for cmd in commands if cmd not in UI_COMMANDS and not cmd.startswith("escribir:")]
        if unknown:
            return {"status": "error", "detail": f"Not executed: unknown UI commands {unknown}."}

        try:
            for cmd in commands:
                if cmd == "win":
                    pyautogui.press("win")
                    await asyncio.sleep(0.5)
                elif cmd == "enter":
                    pyautogui.press("enter")
                    await asyncio.sleep(0.5)
                elif cmd == "click":
                    pyautogui.click()
                    await asyncio.sleep(0.5)
                elif cmd.startswith("escribir:"):
                    text_to_write = cmd.split("escribir:", 1)[1].strip()
                    pyautogui.write(text_to_write, interval=0.05)
                    await asyncio.sleep(0.5)
            return {"status": "success", "detail": f"Executed UI actions: {commands}"}
        except Exception as e:
            logger.error(f"Error executing UI actions: {e}")
            return {"status": "error", "detail": str(e)}

    async def execute_script(self, command_str) -> dict:
        """
        Runs shell/Python command asynchronously using asyncio subprocess.
        """
        logger.info(f"Running system command: {command_str}")
        if self.is_mock:
            logger.info("[MOCK MODE] Shell command not executed.")
            return {
                "status": "error",
                "detail": "Not executed: ejecutor_izquierdo runs in mock mode (config/arranque.yaml).",
            }
        try:
            # We use shell execution to easily support cross-platform scripts. On POSIX the shell gets its own
            # process group so a timeout can kill everything it spawned.
            session = {} if sys.platform == "win32" else {"start_new_session": True}
            process = await asyncio.create_subprocess_shell(
                command_str, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **session
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=SCRIPT_TIMEOUT_SECONDS)
            except TimeoutError:
                await _kill_process_tree(process)
                logger.warning(f"Command exceeded {SCRIPT_TIMEOUT_SECONDS}s and was killed: {command_str}")
                return {"status": "timeout", "detail": f"Command exceeded {SCRIPT_TIMEOUT_SECONDS}s and was killed."}

            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            exit_code = process.returncode

            logger.info(f"Command execution finished with exit code {exit_code}")
            return {
                "status": "success" if exit_code == 0 else "error",
                "exit_code": exit_code,
                "stdout": stdout_str,
                "stderr": stderr_str,
            }
        except Exception as e:
            logger.error(f"Error executing command script: {e}")
            return {"status": "error", "detail": str(e)}

    async def handle_action(self, event_data, writer):
        """Registers an action request. Nothing runs until a human approves it via APPROVAL_TOPIC."""
        request_id = event_data.get("request_id")
        tool = event_data.get("herramienta")
        logger.info(f"Received action request {request_id} for tool '{tool}'")

        if not request_id:
            logger.warning("Dropping action without request_id: it could never be approved.")
            return
        if tool not in SUPPORTED_TOOLS:
            await self.publish_result(
                writer, request_id, {"status": "error", "detail": f"Tool '{tool}' not supported."}
            )
            return

        self._expire_pending()
        if request_id in self.pending:
            # Never replace a pending request: the human approves what the ticket showed.
            logger.warning(f"Request {request_id} is already pending; ignoring the duplicate.")
            await self.publish_result(
                writer, request_id, {"status": "error", "detail": "Duplicate request_id while pending approval."}
            )
            return

        self.pending[request_id] = (event_data, self._clock())
        logger.info(f"Action {request_id} awaiting human approval.")

    async def handle_approval(self, approval, writer):
        """Runs (approved is True) or discards a pending request. Each request can be decided once."""
        request_id = approval.get("request_id")
        self._expire_pending()
        entry = self.pending.pop(request_id, None)
        if entry is None:
            logger.warning(f"Approval for unknown or expired request {request_id}; ignored.")
            return

        if approval.get("approved") is not True:
            logger.info(f"Action {request_id} rejected by the human reviewer.")
            await self.publish_result(
                writer, request_id, {"status": "rejected", "detail": "Rejected by human reviewer."}
            )
            return

        event_data, _ = entry
        tool = event_data.get("herramienta")
        params = event_data.get("parametros", [])
        logger.info(f"Action {request_id} approved. Executing '{tool}'.")
        if tool == "control_ui":
            result = await self.execute_control_ui(params)
        else:
            cmd_str = params[0] if isinstance(params, list) and len(params) > 0 else str(params)
            result = await self.execute_script(cmd_str)
        await self.publish_result(writer, request_id, result)

    def _expire_pending(self):
        now = self._clock()
        for request_id, (_, created_at) in list(self.pending.items()):
            if now - created_at > PENDING_TTL_SECONDS:
                logger.info(f"Action {request_id} expired without approval.")
                del self.pending[request_id]

    async def publish_result(self, writer, request_id: str, result: dict):
        payload = {
            "action": "publish",
            "topic": RESULT_TOPIC,
            "data": {"request_id": request_id, "resultado": result, "timestamp": time.time()},
        }
        try:
            writer.write((json.dumps(payload) + "\n").encode("utf-8"))
            await writer.drain()
        except Exception as e:
            logger.error(f"Failed to publish execution results: {e}")

    async def run(self):
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                # Subscribe to execution actions and system commands
                subscribe_msg = (
                    json.dumps({"action": "subscribe", "topics": [ACTION_TOPIC, APPROVAL_TOPIC, "system"]}) + "\n"
                )
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                # Read events
                while True:
                    line = await reader.readline()
                    if not line:
                        break

                    event = json.loads(line.decode("utf-8").strip())
                    topic = event.get("topic")
                    data = event.get("data", {})

                    if topic == ACTION_TOPIC:
                        await self.handle_action(data, writer)
                    elif topic == APPROVAL_TOPIC:
                        # Run approved actions in the background so the event loop keeps reading.
                        asyncio.create_task(self.handle_approval(data, writer))
                    elif topic == "system":
                        action = data.get("action")
                        if action == "reload_arranque":
                            try:
                                from core.arranque import read_mock_flag

                                self.is_mock = read_mock_flag("ejecutor_izquierdo") or ("--mock" in sys.argv)
                                logger.info(f"💻 Ejecutor Izquierdo: Estado mock actualizado a {self.is_mock}")
                            except Exception as ex:
                                logger.warning(f"Failed to reload mock settings in Ejecutor: {ex}")
                        elif data.get("command") == "shutdown":
                            logger.info("Shutdown command received. Exiting.")
                            return

            except Exception as e:
                logger.error(f"Connection lost or error in loop: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)


if __name__ == "__main__":
    mock_flag = "--mock" in sys.argv
    ejecutor = EjecutorIzquierdo(is_mock=mock_flag)
    try:
        asyncio.run(ejecutor.run())
    except KeyboardInterrupt:
        logger.info("Ejecutor Izquierdo stopped.")
