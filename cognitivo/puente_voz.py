"""
Voice loop for Visión OS (the core "Jarvis" path).

- canal.sensorial.audio.transcripcion -> canal.cognitivo.entrada as request "voz-<uuid>", so the Amígdala filters it.
  A transcription that only answers a pending Intriga ticket ("sí, procede", "no, abortar") is not a request.
- canal.cognitivo.respuesta for a "voz-" request -> canal.sensorial.audio.hablar (spoken by Habla Parietal).
- canal.seguridad.alerta for a "voz-" request -> a spoken refusal, and the reason is announced on the HUD.
"""

import asyncio
import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from cognitivo.protocolo_intriga import APPROVAL_WORDS, ESTADO_TOPIC, REJECTION_WORDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] PuenteVoz: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("PuenteVoz")

VOICE_REQUEST_PREFIX = "voz-"
TRANSCRIPTION_TOPIC = "canal.sensorial.audio.transcripcion"
SUBSCRIBED_TOPICS = [
    TRANSCRIPTION_TOPIC,
    ESTADO_TOPIC,
    "canal.cognitivo.respuesta",
    "canal.seguridad.alerta",
    "system",
]

Publish = Callable[[str, dict[str, Any]], Awaitable[None]]


class PuenteVoz:
    """Connects speech to the cognitive input and the cognitive answers back to speech."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        self.host = host
        self.port = port
        # Mirrors ProtocoloIntriga: True while a research ticket waits for a spoken or HUD answer.
        self.intriga_pendiente = False

    def answers_intriga_ticket(self, text: str) -> bool:
        if not self.intriga_pendiente:
            return False
        words = text.strip().lower().replace(",", " ").split()
        first = words[0] if words else ""
        return first in APPROVAL_WORDS or first in REJECTION_WORDS

    @staticmethod
    def _is_voice_request(request_id: Any) -> bool:
        return isinstance(request_id, str) and request_id.startswith(VOICE_REQUEST_PREFIX)

    async def handle_event(self, topic: str, data: dict[str, Any], publish: Publish) -> None:
        if topic == ESTADO_TOPIC:
            self.intriga_pendiente = bool(data.get("esperando_confirmacion"))
        elif topic == TRANSCRIPTION_TOPIC:
            await self.handle_transcription(data.get("transcripcion", ""), publish)
        elif topic == "canal.cognitivo.respuesta" and self._is_voice_request(data.get("request_id")):
            await self.handle_response(data, publish)
        elif topic == "canal.seguridad.alerta" and self._is_voice_request(data.get("request_id")):
            await self.handle_blocked(data, publish)

    async def handle_transcription(self, text: str, publish: Publish) -> None:
        text = (text or "").strip()
        if not text or self.answers_intriga_ticket(text):
            return
        await publish(
            "canal.cognitivo.entrada",
            {
                "request_id": f"{VOICE_REQUEST_PREFIX}{uuid.uuid4().hex}",
                "prompt": text,
                "esfuerzo_requerido": "esfuerzo_bajo",
            },
        )

    async def handle_response(self, data: dict[str, Any], publish: Publish) -> None:
        if data.get("status") == "success" and data.get("response"):
            await publish("canal.sensorial.audio.hablar", {"texto": data["response"]})
            return
        error = data.get("error") or "la respuesta llegó vacía"
        logger.error(f"Voice request {data.get('request_id')} failed: {error}")
        await publish("canal.sensorial.audio.hablar", {"texto": "No pude responder a eso."})
        await publish(
            "canal.sistema.anuncios",
            {"mensaje": f"[VOZ] No pude responder: {error}", "timestamp": time.time()},
        )

    async def handle_blocked(self, data: dict[str, Any], publish: Publish) -> None:
        reason = data.get("reason", "petición bloqueada")
        logger.critical(f"Voice request {data.get('request_id')} blocked: {reason}")
        await publish("canal.sensorial.audio.hablar", {"texto": "No puedo procesar esa petición por seguridad."})
        await publish(
            "canal.sistema.anuncios",
            {"mensaje": f"[VOZ] Petición bloqueada por la Amígdala: {reason}", "timestamp": time.time()},
        )

    async def run(self) -> None:
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                writer.write((json.dumps({"action": "subscribe", "topics": SUBSCRIBED_TOPICS}) + "\n").encode("utf-8"))
                await writer.drain()

                async def publish(topic: str, data: dict[str, Any]) -> None:
                    writer.write(
                        (json.dumps({"action": "publish", "topic": topic, "data": data}) + "\n").encode("utf-8")
                    )
                    await writer.drain()

                while True:
                    line = await reader.readline()
                    if not line:
                        break
                    try:
                        event = json.loads(line.decode("utf-8").strip())
                    except json.JSONDecodeError:
                        continue

                    topic = event.get("topic")
                    data = event.get("data", {})
                    if topic == "system" and data.get("command") == "shutdown":
                        logger.info("Shutdown command received. Exiting.")
                        return
                    await self.handle_event(topic, data, publish)

            except Exception as e:
                logger.error(f"Voice loop error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(PuenteVoz().run())
    except KeyboardInterrupt:
        logger.info("Puente Voz stopped.")
