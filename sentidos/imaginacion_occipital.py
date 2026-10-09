import asyncio
import json
import logging
import mimetypes
import os
import sys
import time
import uuid

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Run as a script (core/main.py), the project must be importable before the port is imported.
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.ports.image_generator import GeneratedImage, IImageGenerator, ImageGeneratorError  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] LobeOccipitalImaginacion: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ImaginacionOccipital")

RESPONSE_TOPIC = "canal.imaginacion.respuesta"


class ImaginacionOccipital:
    """
    Answers canal.imaginacion.peticion through an injected IImageGenerator. Every request gets exactly one
    response on canal.imaginacion.respuesta: success with the saved image, or an error with the reason.
    With no generator (or force_mock) nothing is generated and the response says why.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        generator: IImageGenerator | None = None,
        output_dir: str | None = None,
        force_mock: bool = False,
    ):
        self.host = host
        self.port = port
        self.force_mock = force_mock
        self.generator = None if force_mock else generator
        self.output_dir = output_dir or os.path.join(PROJECT_ROOT, "artifacts")
        os.makedirs(self.output_dir, exist_ok=True)

    def _no_generator_reason(self) -> str:
        if self.force_mock:
            return "Image generation is off: mock mode is on for imaginacion_occipital (config/arranque.yaml)."
        return "No image generator is configured for imaginacion_occipital."

    async def _save(self, image: GeneratedImage) -> tuple[str, str]:
        extension = mimetypes.guess_extension(image.mime_type) or ".bin"
        filename = f"imagen-{uuid.uuid4().hex}{extension}"
        path = os.path.join(self.output_dir, filename)
        await asyncio.to_thread(_write_bytes, path, image.data)
        return path, f"/artifacts/{filename}"

    async def _generate_response(self, request_id: str, prompt: str) -> dict:
        if self.generator is None:
            return _error_response(request_id, prompt, self._no_generator_reason(), None)
        try:
            image = await self.generator.generate(prompt)
            path, url = await self._save(image)
        except ImageGeneratorError as e:
            logger.warning(f"Generation failed for {request_id}: {e}")
            return _error_response(request_id, prompt, str(e), self.generator.generator_id)
        except Exception as e:
            logger.exception(f"Unexpected error generating {request_id}")
            return _error_response(
                request_id, prompt, f"Unexpected error while generating the image: {e}", self.generator.generator_id
            )
        logger.info(f"Image for {request_id} saved to {path}")
        return {
            "request_id": request_id,
            "status": "success",
            "prompt": prompt,
            "image_path": path,
            "image_url": url,
            "generator_id": image.generator_id,
            "mime_type": image.mime_type,
            "metadata": image.metadata,
            "timestamp": time.time(),
        }

    async def handle_request(self, event_data, writer):
        request_id = event_data.get("request_id", f"img-{int(time.time())}")
        prompt = event_data.get("prompt")

        if not isinstance(prompt, str) or not prompt.strip():
            logger.error("Missing 'prompt' in request.")
            response = _error_response(request_id, prompt, "Missing 'prompt' in request.", None)
        else:
            logger.info(f"Processing image generation request {request_id} for prompt: '{prompt}'")
            response = await self._generate_response(request_id, prompt)

        await _publish(writer, response, request_id)

    async def run(self):
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                # Subscribe to imagination requests and system shutdown
                subscribe_msg = (
                    json.dumps({"action": "subscribe", "topics": ["canal.imaginacion.peticion", "system"]}) + "\n"
                )
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                while True:
                    line = await reader.readline()
                    if not line:
                        break

                    event = json.loads(line.decode("utf-8").strip())
                    topic = event.get("topic")
                    data = event.get("data", {})

                    if topic == "canal.imaginacion.peticion":
                        asyncio.create_task(self.handle_request(data, writer))
                    elif topic == "system" and data.get("command") == "shutdown":
                        logger.info("Shutdown command received. Exiting.")
                        return

            except Exception as e:
                logger.error(f"Connection lost or error in loop: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)


def _write_bytes(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)


def _error_response(request_id: str, prompt, reason: str, generator_id: str | None) -> dict:
    return {
        "request_id": request_id,
        "status": "error",
        "prompt": prompt,
        "error": reason,
        "generator_id": generator_id,
        "timestamp": time.time(),
    }


async def _publish(writer, data: dict, request_id: str) -> None:
    event = {"action": "publish", "topic": RESPONSE_TOPIC, "data": data}
    try:
        writer.write((json.dumps(event) + "\n").encode("utf-8"))
        await writer.drain()
        logger.info(f"Published {data['status']} response for {request_id}")
    except Exception as e:
        logger.error(f"Failed to publish image response: {e}")


if __name__ == "__main__":
    mock_flag = "--mock" in sys.argv
    generator = None
    if not mock_flag:
        from core.adapters.comfyui_image_generator import comfyui_from_config

        generator = comfyui_from_config()
    imaginacion = ImaginacionOccipital(generator=generator, force_mock=mock_flag)
    try:
        asyncio.run(imaginacion.run())
    except KeyboardInterrupt:
        logger.info("Imaginacion Occipital stopped.")
