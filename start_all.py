import os
import subprocess
import sys
import time


def launch_environment():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    vision_studio_dir = os.path.join(root_dir, "vision_studio")

    print("============================================================")
    print("🚀 Visión OS — Iniciando Entorno Completo (Hexagonal In-Process)")
    print("============================================================")

    # 1. Start Unified Brainstem Orchestrator (core/main.py)
    print("[1/2] Iniciando Orquestador Cerebral Unificado (14 daemons en un solo runtime)...")
    core_proc = subprocess.Popen([sys.executable, "core/main.py"], cwd=root_dir)
    time.sleep(2)

    # 2. Vision Studio Frontend (Tauri)
    print("[2/2] Lanzando Visión Studio Nativo (Tauri Dev)...")
    studio_proc = None
    if os.path.exists(os.path.join(vision_studio_dir, "package.json")):
        studio_proc = subprocess.Popen(["npm", "run", "tauri", "dev"], cwd=vision_studio_dir, shell=True)

    print("\n✅ ¡Entorno Visión OS activo y coordinado!")
    print("Presioná Ctrl+C en esta consola para detener todos los procesos.\n")

    try:
        if studio_proc:
            studio_proc.wait()
        else:
            core_proc.wait()
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo procesos de Visión OS...")
        if studio_proc:
            studio_proc.terminate()
        core_proc.terminate()
        print("👋 Entorno detenido limpiamente.")


if __name__ == "__main__":
    launch_environment()
