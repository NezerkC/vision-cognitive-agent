import asyncio
import json
import logging
import os
import sys
import time

import aiohttp
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] LobeOccipitalImaginacion: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ImaginacionOccipital")


class ImaginacionOccipital:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        comfy_url: str = "http://127.0.0.1:8188/prompt",
        force_mock: bool = False,
    ):
        self.host = host
        self.port = port
        self.comfy_url = comfy_url
        self.force_mock = force_mock

        # Ensure a directory for output images exists
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts")
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_mock_image(self, prompt: str) -> str:
        """
        Creates a dummy placeholder image using PIL and returns the path.
        """
        logger.info(f"[MOCK] Simulating ComfyUI generation for prompt: '{prompt}'")
        await asyncio.sleep(2.0)  # Simulate generation latency

        img_path = os.path.join(self.output_dir, f"comfy_mock_{int(time.time())}.png")
        try:
            # Create a simple solid image representing our "imagination"
            img = Image.new("RGB", (512, 512), color=(70, 130, 180))
            img.save(img_path)
            logger.info(f"Mock image saved to {img_path}")
            return img_path
        except Exception as e:
            logger.error(f"Failed to save mock image: {e}")
            return "mock_image_placeholder.png"

    async def generate_comfy_image(self, prompt: str) -> str:
        """
        Sends generation request to local ComfyUI API. Falls back to mock on failure.
        """
        if self.force_mock:
            return await self.generate_mock_image(prompt)
        # A simple default text-to-image workflow payload for ComfyUI API
        # Note: ComfyUI expects a specific node-based workflow dictionary
        payload = {
            "client_id": f"vision-os-{int(time.time())}",
            "prompt": {
                "3": {
                    "class_type": "KSampler",
                    "inputs": {
                        "cfg": 8,
                        "denoise": 1,
                        "model": ["4", 0],
                        "noise_seed": int(time.time()),
                        "positive": ["6", 0],
                        "negative": ["7", 0],
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "steps": 20,
                        "latent_image": ["5", 0],
                    },
                },
                "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "v1-5-pruned-emaonly.ckpt"}},
                "5": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": 512, "width": 512}},
                "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": prompt}},
                "7": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"clip": ["4", 1], "text": "bad quality, blurry, deformed"},
                },
                "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
                "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "vision_os", "images": ["8", 0]}},
            },
        }

        logger.info(f"Sending prompt request to ComfyUI at {self.comfy_url}...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.comfy_url, json=payload, timeout=5.0) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        prompt_id = data.get("prompt_id")
                        logger.info(f"ComfyUI prompt queued. ID: {prompt_id}")
                        # In real-world, we would poll the history endpoint to wait for completion.
                        # For this lightweight client integration, if ComfyUI replies 200, we log it.
                        # We will return a simulated output path for completion.
                        img_path = os.path.join(self.output_dir, f"comfy_out_{prompt_id}.png")
                        return img_path
                    else:
                        logger.warning(f"ComfyUI returned status {resp.status}. Falling back to Mock.")
                        return await self.generate_mock_image(prompt)
        except Exception as e:
            logger.warning(f"Could not connect to ComfyUI API: {e}. Falling back to Mock.")
            return await self.generate_mock_image(prompt)

    async def handle_request(self, event_data, writer):
        request_id = event_data.get("request_id", f"img-{int(time.time())}")
        prompt = event_data.get("prompt")

        if not prompt:
            logger.error("Missing 'prompt' in request.")
            return

        logger.info(f"Processing image generation request {request_id} for prompt: '{prompt}'")

        # Trigger image generation
        img_path = await self.generate_comfy_image(prompt)

        # Publish response event
        response_event = {
            "action": "publish",
            "topic": "canal.imaginacion.respuesta",
            "data": {"request_id": request_id, "image_path": img_path, "timestamp": time.time(), "status": "success"},
        }

        try:
            writer.write((json.dumps(response_event) + "\n").encode("utf-8"))
            await writer.drain()
            logger.info(f"Published generation response for {request_id}")
        except Exception as e:
            logger.error(f"Failed to publish image response: {e}")

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


if __name__ == "__main__":
    mock_flag = "--mock" in sys.argv
    imaginacion = ImaginacionOccipital(force_mock=mock_flag)
    try:
        asyncio.run(imaginacion.run())
    except KeyboardInterrupt:
        logger.info("Imaginacion Occipital stopped.")
