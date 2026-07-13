import asyncio
import json
import logging
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] HemisferioIzquierdo: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("EjecutorIzquierdo")

# Attempt to load pyautogui safely
pyautogui = None
try:
    import pyautogui
except ImportError:
    logger.warning("pyautogui not installed. UI automation will run in simulated/mock mode.")


class EjecutorIzquierdo:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000, is_mock: bool = False):
        self.host = host
        self.port = port
        self.is_mock = is_mock
        if not pyautogui:
            self.is_mock = True

    async def execute_control_ui(self, commands) -> dict:
        """
        Executes pyautogui keyboard/mouse simulation.
        Visual warning console log printed in red/orange.
        """
        # Red/Orange safety alert
        print("\033[93m" + "="*80 + "\n[ALERTA DE SEGURIDAD] HEMISFERIO IZQUIERDO TOMANDO CONTROL DEL SISTEMA" + "\033[0m")
        print(f"\033[91mComandos UI recibidos: {commands}\033[0m")
        print("\033[93m" + "="*80 + "\033[0m")

        if self.is_mock:
            logger.info("[MOCK MODE] Simulating UI actions without physical execution.")
            return {"status": "success", "detail": "UI commands executed (Simulated)"}

        try:
            for cmd in commands:
                cmd = cmd.strip()
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
                else:
                    logger.warning(f"Comando UI no reconocido: '{cmd}'")
            return {"status": "success", "detail": f"Executed UI actions: {commands}"}
        except Exception as e:
            logger.error(f"Error executing UI actions: {e}")
            return {"status": "error", "detail": str(e)}

    async def execute_script(self, command_str) -> dict:
        """
        Runs shell/Python command asynchronously using asyncio subprocess.
        """
        logger.info(f"Running system command: {command_str}")
        try:
            # We use shell execution to easily support cross-platform scripts
            process = await asyncio.create_subprocess_shell(
                command_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            exit_code = process.returncode

            logger.info(f"Command execution finished with exit code {exit_code}")
            return {
                "status": "success" if exit_code == 0 else "error",
                "exit_code": exit_code,
                "stdout": stdout_str,
                "stderr": stderr_str
            }
        except Exception as e:
            logger.error(f"Error executing command script: {e}")
            return {"status": "error", "detail": str(e)}

    async def handle_action(self, event_data, writer):
        """
        Parses and executes incoming tool execution request.
        """
        request_id = event_data.get("request_id", f"action-{int(time.time())}")
        tool = event_data.get("herramienta")
        params = event_data.get("parametros", [])

        logger.info(f"Received action request {request_id} for tool '{tool}'")
        result = {}

        if tool == "control_ui":
            result = await self.execute_control_ui(params)
        elif tool == "ejecutar_script":
            cmd_str = params[0] if isinstance(params, list) and len(params) > 0 else str(params)
            result = await self.execute_script(cmd_str)
        else:
            result = {"status": "error", "detail": f"Tool '{tool}' not supported."}

        # Publish result to the broker
        payload = {
            "action": "publish",
            "topic": "canal.ejecucion.resultado",
            "data": {
                "request_id": request_id,
                "resultado": result,
                "timestamp": time.time()
            }
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
                subscribe_msg = json.dumps({
                    "action": "subscribe",
                    "topics": ["canal.ejecucion.accion", "system"]
                }) + "\n"
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

                    if topic == "canal.ejecucion.accion":
                        # Execute the tool in the background
                        asyncio.create_task(self.handle_action(data, writer))
                    elif topic == "system" and data.get("command") == "shutdown":
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
