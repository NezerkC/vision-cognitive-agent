import asyncio
import json
import logging
import os
import sys
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] LobeParietalOido: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
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

        # Check if we should enforce mock mode due to missing packages or flag
        if self.force_mock or not (sr and pyaudio and faster_whisper):
            self.force_mock = True
            logger.info("Oído Parietal initialized in MOCK mode.")
        else:
            try:
                # Load Whisper Model (tiny model for fast CPU inference)
                logger.info("Loading local Whisper model (tiny)...")
                self.model = faster_whisper.WhisperModel("tiny", device="cpu", compute_type="int8")
                logger.info("Whisper model loaded successfully.")
            except Exception as e:
                logger.warning(f"Could not load Whisper model: {e}. Falling back to MOCK mode.")
                self.force_mock = True

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

        mock_commands = [
            "abre notepad",
            "corre un script de prueba",
            "hola vision, reporta el estado actual"
        ]
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
                "data": {
                    "transcripcion": command,
                    "timestamp": time.time(),
                    "mock": True
                }
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

                if event.get("topic") == "system":
                    data = event.get("data", {})
                    if data.get("action") == "oido_toggle":
                        self.pausado = data.get("pausado", False)
                        estado = "PAUSADO" if self.pausado else "REANUDADO"
                        logger.info(f"🎙️ Oído Parietal {estado} por comando del sistema.")
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
                subscribe_msg = json.dumps({
                    "action": "subscribe",
                    "topics": ["system"]
                }) + "\n"
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                # Start background reader daemon to intercept system commands
                asyncio.create_task(self.reader_daemon(reader))

                if self.force_mock:
                    await self.run_mock_loop(writer)
                else:
                    # Real microphone capture loop using SpeechRecognition
                    r = sr.Recognizer()
                    mic = sr.Microphone()
                    
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
                                "data": {
                                    "transcripcion": text,
                                    "timestamp": time.time(),
                                    "mock": False
                                }
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
