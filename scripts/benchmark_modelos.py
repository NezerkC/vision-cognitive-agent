import asyncio
import json
import os
import sys
import time

import httpx
import litellm

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCHMARK_PATH = os.path.join(PROJECT_ROOT, "config", "model_benchmarks.json")

# Standard test prompt
TEST_PROMPT = "Responde únicamente con la palabra 'OK'."

async def benchmark_model(model_id: str) -> dict:
    print(f"\n[RUN] Iniciando prueba para: {model_id}...")
    start_time = time.time()

    # We will measure total time taken to load, process and respond
    try:
        # We call LiteLLM directly
        response = await litellm.acompletion(
            model=f"ollama/{model_id}",
            messages=[{"role": "user", "content": TEST_PROMPT}],
            api_base="http://localhost:11434",
            timeout=180.0  # 3 minutes maximum for loading
        )
        elapsed = time.time() - start_time
        reply = response.choices[0].message.content.strip()
        print(f"[OK] Completado en {elapsed:.2f} segundos. Respuesta: '{reply}'")
        return {
            "status": "success",
            "time_seconds": elapsed,
            "response": reply
        }
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[FAIL] Fallo tras {elapsed:.2f} segundos. Error: {e}")
        return {
            "status": "error",
            "time_seconds": elapsed,
            "error": str(e)
        }

async def main():
    print("=" * 60)
    print("CARRERA DE MODELOS OLLAMA - MEDICION DE RENDIMIENTO EN GPU")
    print("=" * 60)

    # 1. Fetch downloaded models
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:11434/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
    except Exception as e:
        print(f"[FAIL] No se pudo conectar a Ollama en localhost:11434: {e}")
        sys.exit(1)

    if not models:
        print("[WARN] No hay modelos descargados en Ollama.")
        sys.exit(0)

    print(f"Modelos detectados para la carrera: {', '.join(models)}")
    results = {}

    for idx, model in enumerate(models):
        print(f"\n[Modelo {idx+1}/{len(models)}]")
        # Warm up/Load and generate
        res = await benchmark_model(model)
        results[model] = res

    # Summarize podium
    print("\n" + "=" * 60)
    print("RESULTADOS DE LA CARRERA (PODIO DE VELOCIDAD)")
    print("=" * 60)

    sorted_results = sorted(
        [(k, v) for k, v in results.items() if v["status"] == "success"],
        key=lambda x: x[1]["time_seconds"]
    )

    for rank, (name, metrics) in enumerate(sorted_results):
        print(f"{rank + 1}. {name}: {metrics['time_seconds']:.2f} segundos")

    # 2. Write benchmark outputs to JSON
    os.makedirs(os.path.dirname(BENCHMARK_PATH), exist_ok=True)
    with open(BENCHMARK_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    print(f"\n[SAVE] Benchmarks guardados en: {BENCHMARK_PATH}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
