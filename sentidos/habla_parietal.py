import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] LobeParietalHabla: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("HablaParietal")

class HablaParietal:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000, force_mock: bool = False):
        self.host = host
        self.port = port
        self.force_mock = force_mock
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.output_device_index = None
        self.tts_engine = "edge-tts"

        self.load_config()

    def load_config(self):
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "hardware_interfaces.json"
            )
            if os.path.exists(config_path):
                with open(config_path, encoding="utf-8") as f:
                    cfg = json.load(f)
                habla_cfg = cfg.get("habla_activa", {})
                self.output_device_index = habla_cfg.get("output_device_index")
                self.tts_engine = habla_cfg.get("tts_engine", "edge-tts")
                logger.info(f"Loaded habla config: device={self.output_device_index}, engine={self.tts_engine}")
        except Exception as e:
            logger.warning(f"Failed to load habla config: {e}. Using defaults.")
            self.output_device_index = None
            self.tts_engine = "edge-tts"

    def play_wav_on_device(self, wav_path: str, device_index: int):
        """Plays a WAV file using PyAudio on a specific output device index."""
        try:
            import wave

            import pyaudio

            if not os.path.exists(wav_path):
                return

            f = wave.open(wav_path, 'rb')
            p = pyaudio.PyAudio()
            try:
                stream = p.open(
                    format=p.get_format_from_width(f.getsampwidth()),
                    channels=f.getnchannels(),
                    rate=f.getframerate(),
                    output=True,
                    output_device_index=device_index
                )
                data = f.readframes(1024)
                while data:
                    stream.write(data)
                    data = f.readframes(1024)
                stream.stop_stream()
                stream.close()
            finally:
                p.terminate()
        except Exception as e:
            logger.error(f"Error playing WAV on device {device_index}: {e}")

    def speak_pyttsx3_sync(self, text: str, device_index: int = None):
        """Synthesizes speech using pyttsx3 and plays it (or routes it to device)."""
        try:
            import pyttsx3
            engine = pyttsx3.init()

            # Select Spanish voice if available
            voices = engine.getProperty('voices')
            es_voice = None
            for voice in voices:
                if 'spanish' in voice.name.lower() or 'es-' in voice.id.lower():
                    es_voice = voice.id
                    break
            if es_voice:
                engine.setProperty('voice', es_voice)

            if device_index is not None:
                # Render to temp WAV file and play via PyAudio on selected device
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    temp_filename = f.name
                try:
                    engine.save_to_file(text, temp_filename)
                    engine.runAndWait()
                    # Release COM object resources before playing
                    del engine
                    self.play_wav_on_device(temp_filename, device_index)
                finally:
                    try:
                        os.remove(temp_filename)
                    except Exception:
                        pass
            else:
                # Play directly on default Windows playback device
                engine.say(text)
                engine.runAndWait()
        except Exception as e:
            logger.error(f"Error in pyttsx3 speech synthesis: {e}")

    async def speak_edge_tts(self, text: str, device_index: int = None):
        """Synthesizes speech using edge-tts (natural cloud) and plays it."""
        try:
            import edge_tts
            # Use a warm, natural Spanish voice
            voice = "es-AR-TomasNeural" # Argentina (voseo!)

            communicate = edge_tts.Communicate(text, voice)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_filename = f.name

            try:
                await communicate.save(temp_filename)

                # If device_index is set, notify that edge-tts plays on default.
                if device_index is not None:
                    logger.warning("edge-tts plays on Windows default audio device. For routing to specific speaker, use pyttsx3 motor.")

                # Play using PowerShell MediaPlayer (no external player needed)
                loop = asyncio.get_running_loop()
                def _play():
                    cmd = f"Add-Type -AssemblyName presentationCore; $player = New-Object System.Windows.Media.MediaPlayer; $player.Open('{temp_filename}'); $player.Play(); while ($player.NaturalDuration.HasTimeSpan -eq $false) {{ Start-Sleep -Milliseconds 100 }}; Start-Sleep -Seconds ($player.NaturalDuration.TimeSpan.TotalSeconds + 0.5)"
                    subprocess.run(["powershell", "-Command", cmd], capture_output=True)

                await loop.run_in_executor(self.executor, _play)
            finally:
                try:
                    os.remove(temp_filename)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error in edge-tts speech synthesis: {e}. Falling back to pyttsx3.")
            # Fallback to pyttsx3 local engine
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self.executor, self.speak_pyttsx3_sync, text, device_index)

    async def speak(self, text: str):
        """Main speaking logic (routes to edge-tts or pyttsx3)."""
        if self.force_mock:
            logger.info(f"[🗣️ HABLA PARIETAL - MOCK] Sintetizando voz: '{text}'")
            return

        logger.info(f"Synthesizing voice: '{text}' using {self.tts_engine}")
        if self.tts_engine == "edge-tts":
            await self.speak_edge_tts(text, self.output_device_index)
        else:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self.executor, self.speak_pyttsx3_sync, text, self.output_device_index)

    async def run(self):
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                # Subscribe to voice command output and system updates
                subscribe_msg = json.dumps({
                    "action": "subscribe",
                    "topics": ["canal.sensorial.audio.hablar", "system"]
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

                    if topic == "canal.sensorial.audio.hablar":
                        text = data.get("texto", "")
                        if text:
                            # Speak in background to avoid blocking socket reading
                            asyncio.create_task(self.speak(text))

                    elif topic == "system":
                        action = data.get("action")
                        if action == "reload_hardware_config":
                            logger.info("Reloading hardware configuration...")
                            self.load_config()
                        elif action == "reload_arranque":
                            # We can reload mock mode from config if it changed
                            try:
                                arr_path = os.path.join(
                                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "config",
                                    "arranque.yaml"
                                )
                                if os.path.exists(arr_path):
                                    with open(arr_path, encoding="utf-8") as f:
                                        import yaml
                                        cfg = yaml.safe_load(f)
                                    mock_flag = cfg.get("modos_mock", {}).get("habla_parietal", True)
                                    self.force_mock = mock_flag or ("--mock" in sys.argv)
                                    logger.info(f"Updated mock mode: {self.force_mock}")
                            except Exception as ex:
                                logger.warning(f"Failed to reload mock settings: {ex}")

            except Exception as e:
                logger.error(f"Error in habla loop: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

if __name__ == "__main__":
    import yaml
    mock_flag = "--mock" in sys.argv

    if not mock_flag:
        try:
            arr_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "arranque.yaml"
            )
            if os.path.exists(arr_path):
                with open(arr_path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                mock_flag = cfg.get("modos_mock", {}).get("habla_parietal", True)
        except Exception:
            pass

    habla = HablaParietal(force_mock=mock_flag)
    try:
        asyncio.run(habla.run())
    except KeyboardInterrupt:
        logger.info("Habla Parietal stopped.")
