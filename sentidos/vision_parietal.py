import asyncio
import json
import logging
import os
import sys
import time
import base64
import io
from PIL import Image, ImageChops, ImageStat
import mss

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] LobeParietal: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("VisionParietal")

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "hardware_interfaces.json"
)

class VisionParietal:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000, force_mock: bool = False):
        self.host = host
        self.port = port
        self.force_mock = force_mock
        
        # Capture settings
        self.interval = 5.0
        self.monitor_index = 1
        self.diff_threshold = 0.01
        self.load_config()

        self.last_image = None
        self.sct = None
        
        if not self.force_mock:
            try:
                self.sct = mss.mss()
                logger.info(f"Initialized mss screen capture. Monitors detected: {len(self.sct.monitors) - 1}")
            except Exception as e:
                logger.warning(f"Could not initialize mss screen capture ({e}). Falling back to mock generator.")
                self.force_mock = True

    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            vision_cfg = cfg.get("vision_activa", {})
            self.interval = float(vision_cfg.get("interval_seconds", 5.0))
            self.monitor_index = int(vision_cfg.get("monitor_index", 1))
            self.diff_threshold = float(vision_cfg.get("difference_threshold", 0.01))
            logger.info(f"Loaded config: interval={self.interval}s, monitor={self.monitor_index}, threshold={self.diff_threshold}")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}. Using default values.")

    def capture_screenshot(self) -> Image.Image:
        if self.force_mock:
            # Generate dummy solid color image representing mock screen
            img = Image.new("RGB", (320, 240), color=(10, 30, 80))
            return img

        try:
            # Check monitor boundary
            if self.monitor_index >= len(self.sct.monitors):
                logger.warning(f"Monitor {self.monitor_index} not found. Defaulting to monitor 1.")
                monitor = self.sct.monitors[1]
            else:
                monitor = self.sct.monitors[self.monitor_index]
            
            sct_img = self.sct.grab(monitor)
            # Convert mss format to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            return img
        except Exception as e:
            logger.error(f"Error grabbing screenshot: {e}. Falling back to mock image.")
            return Image.new("RGB", (320, 240), color=(10, 30, 80))

    def has_changed(self, current_img: Image.Image) -> bool:
        if self.force_mock:
            return True

        if self.last_image is None:
            return True

        try:
            # Downsample and convert to grayscale for fast pixel difference comparison
            size = (32, 32)
            curr_thumb = current_img.resize(size).convert("L")
            last_thumb = self.last_image.resize(size).convert("L")
            
            diff = ImageChops.difference(curr_thumb, last_thumb)
            stat = ImageStat.Stat(diff)
            mean_diff = stat.mean[0] / 255.0  # normalized to [0, 1]
            
            logger.debug(f"Normalized screenshot pixel difference: {mean_diff:.4f}")
            return mean_diff > self.diff_threshold
        except Exception as e:
            logger.error(f"Error checking image difference: {e}")
            return True

    def image_to_base64(self, img: Image.Image) -> str:
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=70)  # Compress to JPEG to save bandwidth
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    async def run(self):
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                # Register system topics
                subscribe_msg = json.dumps({
                    "action": "subscribe",
                    "topics": ["system"]
                }) + "\n"
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                while True:
                    loop_start = time.time()
                    
                    # Capture frame in threadpool to avoid blocking event loop
                    loop = asyncio.get_running_loop()
                    img = await loop.run_in_executor(None, self.capture_screenshot)

                    if self.has_changed(img):
                        logger.info("Visual change detected. Processing and transmitting frame...")
                        self.last_image = img
                        
                        # Base64 encode
                        img_b64 = await loop.run_in_executor(None, self.image_to_base64, img)
                        
                        # Publish screen capture event
                        payload = {
                            "action": "publish",
                            "topic": "canal.sensorial.vision",
                            "data": {
                                "image": img_b64,
                                "timestamp": time.time(),
                                "mock": self.force_mock
                            }
                        }
                        writer.write((json.dumps(payload) + "\n").encode("utf-8"))
                        await writer.drain()
                        logger.info("Screenshot transmitted.")
                    else:
                        logger.debug("No screen change detected. Skipping transmission.")

                    # Calculate remaining sleep time to maintain interval frequency
                    elapsed = time.time() - loop_start
                    sleep_time = max(0.1, self.interval - elapsed)
                    await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in LobeParietal loop: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

if __name__ == "__main__":
    mock_flag = "--mock" in sys.argv
    parietal = VisionParietal(force_mock=mock_flag)
    try:
        asyncio.run(parietal.run())
    except KeyboardInterrupt:
        logger.info("Lóbulo Parietal (Vision) stopped.")
