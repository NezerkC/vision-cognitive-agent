import asyncio
import base64
import io
import json
import logging
import os
import sys
import time

import mss
from PIL import Image, ImageChops, ImageStat

# Attempt to load OpenCV
cv2 = None
try:
    import cv2
except ImportError:
    pass

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
        self.pausado = False

        # Camera settings
        self.camara_activa = False
        self.camara_index = 0
        self.camera_ip = ""
        self.cap = None
        self.last_camera_settings = None

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
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            vision_cfg = cfg.get("vision_activa", {})
            self.interval = float(vision_cfg.get("interval_seconds", 5.0))
            self.monitor_index = int(vision_cfg.get("monitor_index", 1))
            self.diff_threshold = float(vision_cfg.get("difference_threshold", 0.01))

            # Load camera settings
            self.camara_activa = vision_cfg.get("camara_activa", False)
            self.camara_index = int(vision_cfg.get("camara_index", 0))
            self.camera_ip = vision_cfg.get("camera_ip", "").strip()

            logger.info(f"Loaded config: interval={self.interval}s, monitor={self.monitor_index}, threshold={self.diff_threshold}, camera={self.camara_activa} (index={self.camara_index}, IP='{self.camera_ip}')")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}. Using default values.")

    def capture_camera(self) -> str:
        """
        Grabs a frame from the camera (local or IP), encodes it as base64, and returns it.
        Returns an empty string on error or if disabled.
        """
        if not self.camara_activa or cv2 is None or self.force_mock:
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            return ""

        current_settings = (self.camara_index, self.camera_ip)
        if self.cap is not None and self.last_camera_settings != current_settings:
            logger.info("Camera settings changed. Re-opening camera...")
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        try:
            if self.cap is None:
                if self.camera_ip:
                    logger.info(f"Opening camera by IP/URL: {self.camera_ip}")
                    self.cap = cv2.VideoCapture(self.camera_ip)
                else:
                    logger.info(f"Opening physical/virtual camera on index {self.camara_index} with DirectShow")
                    self.cap = cv2.VideoCapture(self.camara_index, cv2.CAP_DSHOW)
                self.last_camera_settings = current_settings

            if not self.cap.isOpened():
                logger.warning(f"Could not open camera {current_settings}")
                self.cap = None
                return ""

            ret, frame = self.cap.read()
            if not ret:
                logger.warning("Could not read frame from camera.")
                # Force re-opening next time
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
                return ""

            # Resize frame to save bandwidth
            h, w = frame.shape[:2]
            if w > 640:
                scale = 640.0 / w
                frame = cv2.resize(frame, (640, int(h * scale)))

            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ret:
                return ""

            return base64.b64encode(buffer).decode('utf-8')
        except Exception as e:
            logger.error(f"Error capturing camera frame: {e}")
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            return ""

    async def reader_daemon(self, reader):
        """
        Background task to intercept system events (config reload) on the socket.
        """
        try:
            while reader and not reader.at_eof():
                line = await asyncio.wait_for(reader.readline(), timeout=60.0)
                if not line:
                    break
                try:
                    event = json.loads(line.decode("utf-8").strip())
                except json.JSONDecodeError:
                    continue

                topic = event.get("topic")
                data = event.get("data", {})

                if topic == "canal.sistema.comando":
                    comando = data.get("comando")
                    accion = data.get("accion")
                    if comando == "vision":
                        if accion == "pausar":
                            self.pausado = True
                            logger.info("👁️ Visión Parietal PAUSADA por comando de canal.sistema.comando.")
                        elif accion == "reanudar":
                            self.pausado = False
                            logger.info("👁️ Visión Parietal REANUDADA por comando de canal.sistema.comando.")
                        elif accion == "frecuencia":
                            self.interval = float(data.get("valor", 5.0))
                            logger.info(f"👁️ Visión Parietal: intervalo de captura cambiado a {self.interval}s.")

                elif topic == "system":
                    action = data.get("action")
                    if action == "reload_hardware_config":
                        logger.info("👁️ Visión Parietal: Recargando configuración de hardware...")
                        self.load_config()
                    elif action == "reload_arranque":
                        try:
                            arr_path = os.path.join(
                                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config",
                                "arranque.yaml"
                            )
                            if os.path.exists(arr_path):
                                with open(arr_path, encoding="utf-8") as f:
                                    import yaml
                                    arr_cfg = yaml.safe_load(f)
                                mock_flag = arr_cfg.get("modos_mock", {}).get("vision_parietal", True)
                                self.force_mock = mock_flag or ("--mock" in sys.argv)
                                logger.info(f"👁️ Visión Parietal: Estado mock actualizado a {self.force_mock}")
                        except Exception as ex:
                            logger.warning(f"Failed to reload mock settings in Vision: {ex}")
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.error(f"Reader daemon error: {e}")

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
                    "topics": ["system", "canal.sistema.comando"]
                }) + "\n"
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                # Start background reader daemon
                asyncio.create_task(self.reader_daemon(reader))

                while True:
                    loop_start = time.time()

                    if self.pausado:
                        await asyncio.sleep(0.5)
                        continue

                    # Capture frame in threadpool to avoid blocking event loop
                    loop = asyncio.get_running_loop()
                    img = await loop.run_in_executor(None, self.capture_screenshot)
                    screen_changed = self.has_changed(img)

                    cam_b64 = await loop.run_in_executor(None, self.capture_camera)

                    if screen_changed or cam_b64:
                        logger.info("Visual change or camera frame detected. Processing and transmitting...")
                        if screen_changed:
                            self.last_image = img
                            img_b64 = await loop.run_in_executor(None, self.image_to_base64, img)
                            self.last_img_b64 = img_b64
                        else:
                            if not hasattr(self, 'last_img_b64') or self.last_img_b64 is None:
                                self.last_img_b64 = await loop.run_in_executor(None, self.image_to_base64, img)
                            img_b64 = self.last_img_b64

                        # Publish combined vision capture event
                        payload = {
                            "action": "publish",
                            "topic": "canal.sensorial.vision",
                            "data": {
                                "image": img_b64,
                                "camera_image": cam_b64,
                                "timestamp": time.time(),
                                "mock": self.force_mock,
                                "cambio_detectado": screen_changed
                            }
                        }
                        writer.write((json.dumps(payload) + "\n").encode("utf-8"))
                        await writer.drain()
                        logger.info("Vision packet transmitted.")
                    else:
                        logger.debug("No visual changes. Skipping transmission.")

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
