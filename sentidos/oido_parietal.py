import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] LobeParietalOido: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("OidoParietal")

# Attempt to load optional speech recognition packages safely
sr = None
pyaudio = None
faster_whisper = None

try:
    import speech_recognition as sr
except ImportError:
    logger.warning("speech_recognition not installed. Running in mock mode.")

try:
    import pyaudio
except ImportError:
    logger.warning("pyaudio not installed. Running in mock mode.")

try:
    import faster_whisper
except ImportError:
    logger.warning("faster-whisper not installed. Running in mock mode.")


class OidoParietal:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000, force_mock: bool = False):
        self.host = host
        self.port = port
        self.force_mock = force_mock
        self.model = None
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Pause/resume control (set by system commands via broker)
        self.pausado = False

        self.input_device_index = None
        self.energy_threshold = 300
        self.dynamic_energy_threshold = True
        self.whisper_model = "tiny"

        self.load_config()

        # Check if we should enforce mock mode due to missing packages or flag
        if self.force_mock or not (sr and pyaudio and faster_whisper):
            self.force_mock = True
            logger.info("Oído Parietal initialized in MOCK mode.")
        else:
            try:
                # Load Whisper Model
                logger.info(f"Loading local Whisper model ({self.whisper_model})...")
                self.model = faster_whisper.WhisperModel(self.whisper_model, device="cpu", compute_type="int8")
                logger.info("Whisper model loaded successfully.")
            except Exception as e:
                logger.warning(f"Could not load Whisper model: {e}. Falling back to MOCK mode.")
                self.force_mock = True

    def load_config(self):
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "hardware_interfaces.json"
            )
            if os.path.exists(config_path):
                with open(config_path, encoding="utf-8") as f:
                    cfg = json.load(f)
                oido_cfg = cfg.get("oido_activo", {})
                self.input_device_index = oido_cfg.get("input_device_index")
                self.energy_threshold = oido_cfg.get("energy_threshold", 300)
                self.dynamic_energy_threshold = oido_cfg.get("dynamic_energy_threshold", True)
                self.whisper_model = oido_cfg.get("whisper_model", "tiny")
                logger.info(
                    f"Loaded oido config: device={self.input_device_index}, threshold={self.energy_threshold}, model={self.whisper_model}"
                )
            else:
                self.input_device_index = None
                self.energy_threshold = 300
                self.dynamic_energy_threshold = True
                self.whisper_model = "tiny"
        except Exception as e:
            logger.warning(f"Failed to load oido config: {e}. Using defaults.")
            self.input_device_index = None
            self.energy_threshold = 300
            self.dynamic_energy_threshold = True
            self.whisper_model = "tiny"

    def transcribe_audio_sync(self, audio_data) -> str:
        """
        Synchronous transcription logic called inside the ThreadPoolExecutor.
        """
        try:
            # Write audio bytes to a temporary wav file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_filename = f.name
                f.write(audio_data.get_wav_data())

            # Transcribe with Whisper
            segments, info = self.model.transcribe(temp_filename, beam_size=5)
            text_segments = [segment.text for segment in segments]
            text = " ".join(text_segments).strip()

            # Clean up temp file
            try:
                os.remove(temp_filename)
            except Exception:
                pass

            return text
        except Exception as e:
            logger.error(f"Error during audio transcription: {e}")
            return ""

    async def run_mock_loop(self, writer):
        """
        Simulates periodic voice commands from the user to verify broker event routing.
        """
        if "--mock" not in sys.argv:
            logger.info("[Oído Parietal] Running silent idle loop (no microphone hardware available).")
            while True:
                await asyncio.sleep(60)

        mock_commands = ["abre notepad", "corre un script de prueba", "hola vision, reporta el estado actual"]
        cmd_idx = 0

        while True:
            # If paused, skip mock dictation
            if self.pausado:
                await asyncio.sleep(0.5)
                continue

            await asyncio.sleep(12.0)
            command = mock_commands[cmd_idx]
            cmd_idx = (cmd_idx + 1) % len(mock_commands)

            logger.info(f"[Oído Parietal] (MOCK Dictation) Transcribed text: '{command}'")

            payload = {
                "action": "publish",
                "topic": "canal.sensorial.audio.transcripcion",
                "data": {"transcripcion": command, "timestamp": time.time(), "mock": True},
            }
            try:
                writer.write((json.dumps(payload) + "\n").encode("utf-8"))
                await writer.drain()
            except Exception as e:
                logger.error(f"Failed to publish mock transcription: {e}")
                break

    async def reader_daemon(self, reader):
        """
        Background task that reads broker messages and processes system commands
        (like oido_toggle for pause/resume) without blocking the main loop.
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
                    if comando == "oido":
                        if accion == "pausar":
                            self.pausado = True
                            logger.info("🎙️ Oído Parietal PAUSADO por comando de canal.sistema.comando.")
                        elif accion == "reanudar":
                            self.pausado = False
                            logger.info("🎙️ Oído Parietal REANUDADO por comando de canal.sistema.comando.")

                elif topic == "system":
                    action = data.get("action")
                    if action == "oido_toggle":
                        self.pausado = data.get("pausado", False)
                        estado = "PAUSADO" if self.pausado else "REANUDADO"
                        logger.info(f"🎙️ Oído Parietal {estado} por comando del sistema.")
                    elif action == "reload_hardware_config":
                        logger.info("🎙️ Oído Parietal: Recargando configuración de hardware...")
                        self.load_config()
                    elif action == "reload_arranque":
                        try:
                            arr_path = os.path.join(
                                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "arranque.yaml"
                            )
                            if os.path.exists(arr_path):
                                with open(arr_path, encoding="utf-8") as f:
                                    import yaml

                                    arr_cfg = yaml.safe_load(f)
                                mock_flag = arr_cfg.get("modos_mock", {}).get("oido_parietal", True)
                                self.force_mock = mock_flag or ("--mock" in sys.argv)
                                logger.info(f"🎙️ Oído Parietal: Estado mock actualizado a {self.force_mock}")
                        except Exception as ex:
                            logger.warning(f"Failed to reload mock settings in Oido: {ex}")
        except asyncio.TimeoutError:
            pass  # No message within timeout — reader_daemon keeps running
        except Exception as e:
            logger.error(f"Reader daemon error: {e}")

    async def run(self):
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                # Subscribe to system commands
                subscribe_msg = (
                    json.dumps({"action": "subscribe", "topics": ["system", "canal.sistema.comando"]}) + "\n"
                )
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                # Start background reader daemon to intercept system commands
                asyncio.create_task(self.reader_daemon(reader))

                if self.force_mock:
                    await self.run_mock_loop(writer)
                else:
                    # Real microphone capture loop using SpeechRecognition
                    r = sr.Recognizer()
                    r.energy_threshold = self.energy_threshold
                    r.dynamic_energy_threshold = self.dynamic_energy_threshold

                    mic = sr.Microphone(device_index=self.input_device_index)

                    logger.info("Microphone listener calibrated. Starting listening loop...")
                    with mic as source:
                        r.adjust_for_ambient_noise(source, duration=1.0)

                    loop = asyncio.get_running_loop()

                    while True:
                        # If paused, skip listening and just wait
                        if self.pausado:
                            await asyncio.sleep(0.5)
                            continue

                        logger.info("Listening for voice input...")
                        try:
                            # Use timeout so pause flag can be checked between listen attempts
                            audio = await loop.run_in_executor(
                                None, lambda: r.listen(source, timeout=1.0, phrase_time_limit=5.0)
                            )
                        except sr.WaitTimeoutError:
                            # No speech detected within timeout — just loop
                            continue

                        if audio is None:
                            continue

                        logger.info("Voice input captured. Transcribing...")

                        # Run Whisper transcription in executor to keep event loop responsive
                        text = await loop.run_in_executor(self.executor, self.transcribe_audio_sync, audio)

                        if text:
                            logger.info(f"[Oído Parietal] Transcribed text: '{text}'")
                            payload = {
                                "action": "publish",
                                "topic": "canal.sensorial.audio.transcripcion",
                                "data": {"transcripcion": text, "timestamp": time.time(), "mock": False},
                            }
                            writer.write((json.dumps(payload) + "\n").encode("utf-8"))
                            await writer.drain()

            except Exception as e:
                logger.error(f"Error in OidoParietal loop: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)


if __name__ == "__main__":
    mock_flag = "--mock" in sys.argv
    oido = OidoParietal(force_mock=mock_flag)
    try:
        asyncio.run(oido.run())
    except KeyboardInterrupt:
        logger.info("Oído Parietal stopped.")
