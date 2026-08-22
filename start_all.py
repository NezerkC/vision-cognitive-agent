import subprocess
import sys
import time
import os

def launch_environment():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    vision_studio_dir = os.path.join(root_dir, "vision_studio")

    print("============================================================")
    print("🚀 Vision OS — Iniciando Entorno Completo")
    print("============================================================")

    # 1. Broker de Eventos
    print("[1/3] Lanzando Broker de Eventos (Puerto 5000)...")
    broker_proc = subprocess.Popen([sys.executable, "core/broker_eventos.py"], cwd=root_dir)
    time.sleep(2)

    # 2. LLM Router
    print("[2/3] Lanzando LLM Router...")
    router_proc = subprocess.Popen([sys.executable, "cognitivo/llm_router.py"], cwd=root_dir)
    time.sleep(1)

    # 3. Vision Studio Frontend (Tauri)
    print("[3/3] Lanzando Visión Studio Nativo (Tauri Dev)...")
    studio_proc = subprocess.Popen(["npm", "run", "tauri", "dev"], cwd=vision_studio_dir, shell=True)

    print("\n✅ ¡Todos los subprocesos están activos!")
    print("Presioná Ctrl+C en esta consola para detener todos los procesos.\n")

    try:
        studio_proc.wait()
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo procesos de Vision OS...")
        studio_proc.terminate()
        router_proc.terminate()
        broker_proc.terminate()
        print("👋 Entorno detenido limpiamente.")

if __name__ == "__main__":
    launch_environment()
