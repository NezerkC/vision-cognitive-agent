import asyncio
import json
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Amigdala: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Amigdala")

# List of signatures indicating prompt injection or forbidden OS actions
FORBIDDEN_SIGNATURES = [
    "ignora tus instrucciones",
    "ignore all instructions",
    "ignore previous instructions",
    "rm -rf",
    "sudo ",
    "borra el sistema",
    "delete database",
    "drop database",
    "drop table"
]

class Amigdala:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        self.host = host
        self.port = port

    def check_prompt_injection(self, prompt: str) -> tuple[bool, str]:
        """
        Scans prompt text for forbidden signatures.
        Returns (is_unsafe, matching_signature)
        """
        lowered_prompt = prompt.lower()
        for sig in FORBIDDEN_SIGNATURES:
            if sig in lowered_prompt:
                return True, sig
        return False, ""

    async def trigger_panic_purge(self, writer: asyncio.StreamWriter):
        """
        Sends a purge command to the broker to clear message queues.
        """
        logger.critical("PANIC SYSTEM ACTIVATED: Requesting event broker purge!")
        purge_command = {"action": "purge"}
        try:
            writer.write((json.dumps(purge_command) + "\n").encode("utf-8"))
            await writer.drain()
            
            # Broadcast the alert to safety channels
            alert_event = {
                "action": "publish",
                "topic": "canal.seguridad.alerta",
                "data": {
                    "status": "PANIC_ACTIVATED",
                    "message": "Global queue purge triggered by user panic command."
                }
            }
            writer.write((json.dumps(alert_event) + "\n").encode("utf-8"))
            await writer.drain()
        except Exception as e:
            logger.error(f"Failed to transmit panic purge command: {e}")

    async def run(self):
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port, limit=16 * 1024 * 1024)
                logger.info("Connected to event broker.")

                # Subscribe to inputs and panic trigger channels
                subscribe_msg = json.dumps({
                    "action": "subscribe",
                    "topics": [
                        "canal.cognitivo.entrada",
                        "canal.seguridad.panic"
                    ]
                }) + "\n"
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                while True:
                    line = await reader.readline()
                    if not line:
                        logger.warning("Broker closed connection.")
                        break

                    try:
                        event = json.loads(line.decode("utf-8").strip())
                    except json.JSONDecodeError:
                        continue

                    topic = event.get("topic")
                    data = event.get("data", {})

                    if topic == "canal.seguridad.panic":
                        await self.trigger_panic_purge(writer)
                        continue

                    if topic == "canal.cognitivo.entrada":
                        request_id = data.get("request_id")
                        prompt = data.get("prompt", "")
                        effort = data.get("esfuerzo_requerido", "esfuerzo_bajo")
                        mock = data.get("mock", False)

                        if not request_id:
                            logger.error("Missing request_id in entrada event.")
                            continue

                        # Check for injection
                        is_unsafe, match_sig = self.check_prompt_injection(prompt)
                        if is_unsafe:
                            logger.critical(f"PROMPT INJECTION BLOCKED for request {request_id}: Found signature '{match_sig}'")
                            
                            # Publish safety alert
                            alert_event = {
                                "action": "publish",
                                "topic": "canal.seguridad.alerta",
                                "data": {
                                    "request_id": request_id,
                                    "status": "BLOCKED",
                                    "reason": f"Prompt injection signature detected: {match_sig}",
                                    "compromised_prompt": prompt
                                }
                            }
                            writer.write((json.dumps(alert_event) + "\n").encode("utf-8"))
                            await writer.drain()
                        else:
                            # Forward safe prompt to the LLM Router
                            logger.info(f"Prompt safe for request {request_id}. Forwarding to LLM Router.")
                            forward_event = {
                                "action": "publish",
                                "topic": "canal.cognitivo.peticion",
                                "data": {
                                    "request_id": request_id,
                                    "prompt": prompt,
                                    "esfuerzo_requerido": effort,
                                    "mock": mock
                                }
                            }
                            writer.write((json.dumps(forward_event) + "\n").encode("utf-8"))
                            await writer.drain()

            except Exception as e:
                logger.error(f"Error in Amigdala loop: {e}. Retrying connection in 5 seconds...")
                await asyncio.sleep(5)

if __name__ == "__main__":
    amigdala = Amigdala()
    try:
        asyncio.run(amigdala.run())
    except KeyboardInterrupt:
        logger.info("Amígdala (Safety Monitor) stopped.")
