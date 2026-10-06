import asyncio
import json
import logging
import sys
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Amigdala: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
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
    "drop table",
]


class Amigdala:
    """
    Amígdala (Perimeter Safety Monitor & Injection Interceptor).
    Implements ISafetyGuard and supports in-memory event dispatch and TCP connections.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        self.host = host
        self.port = port

    def check_prompt_injection(self, prompt: str) -> tuple[bool, str]:
        """
        Scans prompt text for forbidden signatures.
        Returns (is_unsafe, matching_signature)
        """
        lowered_prompt = (prompt or "").lower()
        for sig in FORBIDDEN_SIGNATURES:
            if sig in lowered_prompt:
                return True, sig
        return False, ""

    def inspect_prompt(self, prompt: str) -> tuple[bool, str]:
        """Port ISafetyGuard implementation."""
        return self.check_prompt_injection(prompt)

    def is_safe_command(self, command: str) -> bool:
        """Port ISafetyGuard command verification."""
        is_unsafe, _ = self.check_prompt_injection(command)
        return not is_unsafe

    async def trigger_panic_purge(self, writer: asyncio.StreamWriter | None = None, event_bus: Any = None):
        """
        Sends a purge command to the broker or event bus to clear message queues.
        """
        logger.critical("PANIC SYSTEM ACTIVATED: Requesting event broker purge!")
        purge_event = {"action": "purge"}
        if event_bus:
            await event_bus.purge()
        elif writer:
            writer.write((json.dumps(purge_event) + "\n").encode("utf-8"))
            await writer.drain()

    async def handle_cognitive_input(self, data: dict[str, Any], publish_fn: Any):
        """
        Core security logic: checks for prompt injections and forwards safe payloads
        while PRESERVING multimodal inputs (such as image_base64).
        """
        request_id = data.get("request_id")
        prompt = data.get("prompt", "")
        effort = data.get("esfuerzo_requerido", "esfuerzo_bajo")
        image_base64 = data.get("image_base64")
        mock = data.get("mock", False)

        if not request_id:
            logger.error("Missing request_id in entrada event.")
            return

        is_unsafe, match_sig = self.check_prompt_injection(prompt)
        if is_unsafe:
            logger.critical(f"PROMPT INJECTION BLOCKED for request {request_id}: Found signature '{match_sig}'")
            alert_event = {
                "request_id": request_id,
                "status": "BLOCKED",
                "reason": f"Prompt injection signature detected: {match_sig}",
                "compromised_prompt": prompt,
            }
            await publish_fn("canal.seguridad.alerta", alert_event)
        else:
            logger.info(
                f"Prompt safe for request {request_id}. Forwarding to LLM Router (multimodal={bool(image_base64)})."
            )
            forward_event = {
                "request_id": request_id,
                "prompt": prompt,
                "esfuerzo_requerido": effort,
                "image_base64": image_base64,
                "mock": mock,
            }
            await publish_fn("canal.cognitivo.peticion", forward_event)

    async def run(self):
        """Standalone TCP client loop for backwards compatibility."""
        while True:
            try:
                logger.info(f"Connecting to event broker at {self.host}:{self.port}...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                # Register subscriptions
                subscribe_msg = (
                    json.dumps({"action": "subscribe", "topics": ["canal.cognitivo.entrada", "canal.seguridad.panic"]})
                    + "\n"
                )
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                async def tcp_publish(topic: str, data: dict[str, Any]):
                    msg = {"action": "publish", "topic": topic, "data": data}
                    writer.write((json.dumps(msg) + "\n").encode("utf-8"))
                    await writer.drain()

                while True:
                    line = await reader.readline()
                    if not line:
                        logger.warning("Connection closed by server.")
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
                        await self.handle_cognitive_input(data, tcp_publish)

            except Exception as e:
                logger.error(f"Error in Amigdala loop: {e}. Retrying connection in 5 seconds...")
                await asyncio.sleep(5)


if __name__ == "__main__":
    amigdala = Amigdala()
    try:
        asyncio.run(amigdala.run())
    except KeyboardInterrupt:
        logger.info("Amígdala (Safety Monitor) stopped.")
