# Implementation Plan: Vision OS - Phase 6 (Refinamiento Cognitivo y Expansión Sensorial)

This plan implements dynamic configuration parameters (temperatures/emotions), automatic Ollama model downloads, FastAPI event-loop-sharing webhook receiver, ComfyUI image generator, and a standalone mic calibrator.

## Proposed Changes

### 1. Configuration Files

#### [NEW] [effort_levels.json](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/config/effort_levels.json)
- Defines temperature and max token bounds for each effort level:
  - `esfuerzo_bajo`: `{"temperature": 0.5, "max_tokens": 512}`
  - `esfuerzo_medio`: `{"temperature": 0.7, "max_tokens": 1024}`
  - `esfuerzo_alto`: `{"temperature": 0.3, "max_tokens": 2048}`

#### [NEW] [emotions.json](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/config/emotions.json)
- Initial state structure:
  ```json
  {
    "estado": "neutral",
    "intensidad": 0.5
  }
  ```

---

### 2. Cognition Refinements

#### [MODIFY] [llm_router.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/llm_router.py)
- Reads `config/effort_levels.json` and `config/emotions.json` on each incoming request.
- Applies emotion override rules:
  - If state is `"intriga"` or `"creativo"`: Forces temperature to `0.8`.
  - If state is `"lógico"`: Forces temperature to `0.0`.
  - Otherwise, uses values from `effort_levels.json`.
- Automatically calls `gestor_modelos_locales` if a local Ollama model fails to resolve due to not being downloaded.

#### [NEW] [gestor_modelos_locales.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/gestor_modelos_locales.py)
- Exposes an asynchronous function `pull_model_if_missing(model_name)`:
  - Executes `ollama pull <name>` asynchronously.
  - Resolves only when model is fully pulled.
  - In mock/development mode, logs the download and resolves immediately.

---

### 3. Senses & Webhooks

#### [NEW] [imaginacion_occipital.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/sentidos/imaginacion_occipital.py)
- Subscribes to `canal.imaginacion.peticion`.
- Executes an asynchronous `POST` request to ComfyUI (`http://127.0.0.1:8188/prompt`).
- Features a mock mode fallback for developer testing when ComfyUI is not running locally.
- Publishes the generated file path to `canal.imaginacion.respuesta`.

#### [NEW] [sistema_periferico.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/sentidos/sistema_periferico.py)
- Builds a FastAPI app running on Uvicorn.
- **Critical Requirement:** Runs uvicorn server within the existing asyncio event loop to share broker event connections without thread locking.
- Exposes `/webhook/externo` (POST) to accept payloads and broadcast them to `canal.sensorial.periferico`.

#### [NEW] [calibrador_audio.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/sentidos/calibrador_audio.py)
- Standalone command-line tool.
- Captures microphone audio using PyAudio and calculates Root Mean Square (RMS) volume levels to print to terminal in real-time.
- Aids in setting up `energy_threshold` calibrators.

---

## Verification Plan

### Automated Test
We will create `core/test_phase6.py` to:
1. Verify emotion overrides by injecting state "lógico" and checking if the router uses temperature 0.0.
2. Inject a test webhook request into our FastAPI system.
3. Assert event publication onto `canal.sensorial.periferico`.
