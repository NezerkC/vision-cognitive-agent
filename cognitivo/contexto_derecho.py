import asyncio
import json
import logging
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] HemisferioDerecho: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ContextoDerecho")

class ContextoDerecho:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        self.host = host
        self.port = port
        self.pending_requests: dict[str, float] = {}

    async def run(self):
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port, limit=16 * 1024 * 1024)
                logger.info("Connected to event broker.")

                # Subscribe to visual sensory feed and LLM responses
                subscribe_msg = json.dumps({
                    "action": "subscribe",
                    "topics": [
                        "canal.sensorial.vision",
                        "canal.cognitivo.respuesta",
                        "system"
                    ]
                }) + "\n"
                writer.write(subscribe_msg.encode("utf-8"))
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

                    if topic == "system" and data.get("action") == "purge":
                        logger.warning("System purge signal received. Resetting pending analyser mappings.")
                        self.pending_requests.clear()
                        continue

                    if topic == "canal.sensorial.vision":
                        img_b64 = data.get("image")
                        mock = data.get("mock", False)
                        ts = data.get("timestamp", time.time())

                        if not img_b64:
                            logger.error("Received vision event with missing image.")
                            continue

                        # Request context interpretation from Lóbulo Frontal (LLM Router)
                        request_id = f"derecho-{int(ts)}"
                        self.pending_requests[request_id] = ts
                        logger.info(f"New screenshot received. Dispatching request {request_id} to LLM Router.")

                        llm_request = {
                            "action": "publish",
                            "topic": "canal.cognitivo.entrada",
                            "data": {
                                "request_id": request_id,
                                "prompt": "¿Qué está haciendo el usuario en esta captura? Si detectas que la pantalla muestra un mensaje de error, advertencia o pop-up de fallo, debes iniciar tu respuesta obligatoriamente con la etiqueta 'ANOMALIA_DETECTADA:' seguida del texto del error.",
                                "image_base64": img_b64,
                                "esfuerzo_requerido": "esfuerzo_bajo",
                                "mock": mock
                            }
                        }
                        writer.write((json.dumps(llm_request) + "\n").encode("utf-8"))
                        await writer.drain()

                    elif topic == "canal.cognitivo.respuesta":
                        request_id = data.get("request_id", "")
                        if request_id.startswith("derecho-"):
                            orig_ts = self.pending_requests.pop(request_id, None)
                            if not orig_ts:
                                continue

                            response_text = data.get("response", "")
                            status = data.get("status", "")

                            if status != "success" or not response_text:
                                logger.error(f"Failed to analyze context for request {request_id}.")
                                continue

                            # Print the required log output format
                            logger.info(f"[Hemisferio Derecho] Contexto actualizado: {response_text}")

                            # Publish the interpreted context to canal.sistema.contexto_actual
                            context_event = {
                                "action": "publish",
                                "topic": "canal.sistema.contexto_actual",
                                "data": {
                                    "contexto": response_text,
                                    "timestamp": time.time()
                                }
                            }
                            writer.write((json.dumps(context_event) + "\n").encode("utf-8"))
                            await writer.drain()

            except Exception as e:
                logger.error(f"Error in HemisferioDerecho loop: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

if __name__ == "__main__":
    derecho = ContextoDerecho()
    try:
        asyncio.run(derecho.run())
    except KeyboardInterrupt:
        logger.info("Hemisferio Derecho (Context Analyser) stopped.")
