import math
import struct
import sys
import time

# Attempt to load PyAudio
pyaudio = None
try:
    import pyaudio
except ImportError:
    pass


def calculate_rms(audio_data: bytes) -> float:
    """
    Computes the Root Mean Square (RMS) volume level of a 16-bit PCM audio buffer.
    Uses pure python math to prevent dependency on the deprecated 'audioop' module.
    """
    if not audio_data:
        return 0.0

    # 16-bit audio means 2 bytes per sample
    count = len(audio_data) // 2
    if count == 0:
        return 0.0

    # Unpack bytes to signed shorts
    fmt = f"{count}h"
    try:
        shorts = struct.unpack(fmt, audio_data)
    except Exception:
        return 0.0

    sum_squares = 0.0
    for sample in shorts:
        # Normalize sample to range [-1.0, 1.0]
        n = sample / 32768.0
        sum_squares += n * n

    rms = math.sqrt(sum_squares / count)
    return rms


def run_calibration():
    print("="*60)
    print("        VISION OS: CALIBRADOR SENSORIAL DE AUDIO (MIC)")
    print("="*60)

    if not pyaudio:
        print("\n[ERROR] PyAudio no está instalado en este entorno.")
        print("Para instalarlo en Windows podés intentar:")
        print("  pip install pipwin")
        print("  pipwin install pyaudio")
        print("\nEjecutando simulación de calibración para demostración:")
        run_mock_calibration()
        return

    # Constants
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = 1024

    p = pyaudio.PyAudio()

    try:
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
    except Exception as e:
        print(f"\n[ERROR] No se pudo abrir el canal del micrófono: {e}")
        print("Asegurate de tener un micrófono conectado y con los drivers instalados.")
        print("\nEjecutando simulación de calibración para demostración:")
        run_mock_calibration()
        return

    print("\nMicrófono calibrado y escuchando... Presioná CTRL+C para detener.")
    print("Hablá al micrófono o hacé ruido para ver los cambios de energía (RMS).\n")
    print(f"{'Volumen (RMS)':<15} | {'Nivel Gráfico':<30}")
    print("-" * 50)

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            rms = calculate_rms(data)

            # Map RMS to a visual bar indicator
            # Max RMS typically scales between 0.0 (silence) and 0.5+ (loud)
            bar_len = int(rms * 100)
            bar = "#" * min(bar_len, 30)

            # Flush stdout for smooth real-time update in terminal
            sys.stdout.write(f"\r{rms:14.6f} | {bar:<30}")
            sys.stdout.flush()
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nCalibración detenida por el usuario.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


def run_mock_calibration():
    print("\n[MOCK] Iniciando simulación de volumen ambiental...")
    print("Presioná CTRL+C para detener.\n")
    print(f"{'Volumen (RMS)':<15} | {'Nivel Gráfico':<30}")
    print("-" * 50)

    mock_values = [0.002, 0.005, 0.012, 0.003, 0.045, 0.080, 0.002, 0.010, 0.150, 0.004]
    idx = 0
    try:
        while True:
            rms = mock_values[idx]
            idx = (idx + 1) % len(mock_values)

            # Add minor random noise
            import random
            rms += random.uniform(-0.001, 0.002)
            rms = max(0.0001, rms)

            bar_len = int(rms * 100)
            bar = "#" * min(bar_len, 30)

            sys.stdout.write(f"\r{rms:14.6f} | {bar:<30}")
            sys.stdout.flush()
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\n\nSimulación de calibración detenida.")


if __name__ == "__main__":
    run_calibration()
