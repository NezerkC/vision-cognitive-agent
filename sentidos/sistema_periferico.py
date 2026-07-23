import asyncio
import json
import logging
import os
import sys
import time
import uvicorn
from fastapi import FastAPI, Request, File, UploadFile, WebSocket, WebSocketDisconnect, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import yaml
import lancedb
import httpx
from dotenv import set_key, find_dotenv
import tempfile
import base64
import litellm
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, TextLoader


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] SistemaPeriferico: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("SistemaPeriferico")

# Instantiate FastAPI application
app = FastAPI(title="Vision OS - Sistema Nervioso Periférico Gateway")

# Enable CORS so browser index.html can upload files and connect to WebSockets locally
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory configurations
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_UPLOAD_DIR = os.path.join(PROJECT_ROOT, "datos_crudos", "temp")
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
GUI_DIR = os.path.join(PROJECT_ROOT, "gui")

app.mount("/artifacts", StaticFiles(directory=ARTIFACTS_DIR), name="artifacts")
if os.path.exists(GUI_DIR):
    app.mount("/gui", StaticFiles(directory=GUI_DIR), name="gui")


def _get_dir_size_gb(path: str) -> float:
    """Recursively calculate directory size in GB."""
    if not os.path.exists(path):
        return 0.0
    total_bytes = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            try:
                total_bytes += os.path.getsize(fp)
            except (OSError, PermissionError):
                pass
    return total_bytes / (1024 ** 3)


@app.get("/")
async def get_index():
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache"
    }
    return FileResponse(os.path.join(GUI_DIR, "index.html"), headers=headers)


@app.get("/graph")
async def get_graph():
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache"
    }
    return FileResponse(os.path.join(GUI_DIR, "graph.html"), headers=headers)


# ---------------------------------------------------------------------------
# Shared state class to manage TCP connections to the Event Broker and
# WebSocket client pool
# ---------------------------------------------------------------------------
class PerifericoGateway:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000, web_port: int = 8000):
        self.host = host
        self.port = port
        self.web_port = web_port
        self.writer = None
        self.reader = None
        self.active_websockets: list[WebSocket] = []

    async def connect_to_broker_loop(self):
        """
        Main loop to connect to the broker, subscribe to topics, and
        broadcast incoming broker events to WebSockets.
        """
        while True:
            try:
                if self.writer is None:
                    self.reader, self.writer = await asyncio.open_connection(self.host, self.port, limit=16 * 1024 * 1024)
                    logger.info("Connected to event broker. Subscribing to system and visual topics...")

                    # Subscribe to all relevant system/sensory/execution topics for the GUI
                    subscribe_msg = json.dumps({
                        "action": "subscribe",
                        "topics": [
                            "canal.sistema.contexto_actual",
                            "canal.sensorial.audio.transcripcion",
                            "canal.ejecucion.accion",
                            "canal.imaginacion.respuesta",
                            "canal.sistema.anuncios",
                            "canal.sensorial.vision",
                            "canal.memoria",
                            "canal.cognitivo.entrada",
                            "canal.cognitivo.peticion",
                            "canal.cognitivo.respuesta",
                            "system"
                        ]
                    }) + "\n"
                    self.writer.write(subscribe_msg.encode("utf-8"))
                    await self.writer.drain()

                # Read events from broker and relay to web clients
                while self.writer is not None:
                    line = await self.reader.readline()
                    if not line:
                        logger.warning("Broker closed connection.")
                        self.writer = None
                        break

                    try:
                        event = json.loads(line.decode("utf-8").strip())
                    except json.JSONDecodeError:
                        continue

                    # Broadcast broker event to all active WebSockets
                    await self.broadcast_to_websockets(event)

            except Exception as e:
                logger.error(f"Failed or disconnected from broker: {e}. Reconnecting in 5 seconds...")
                self.writer = None

            await asyncio.sleep(5)

    async def publish_event(self, topic: str, data: dict) -> bool:
        """
        Helper method to publish an event payload onto the event broker.
        """
        if not self.writer:
            logger.error("Cannot publish: not connected to event broker.")
            return False

        payload = {
            "action": "publish",
            "topic": topic,
            "data": data
        }
        try:
            self.writer.write((json.dumps(payload) + "\n").encode("utf-8"))
            await self.writer.drain()
            return True
        except Exception as e:
            logger.error(f"Failed to publish to broker: {e}")
            self.writer = None
            return False

    async def broadcast_to_websockets(self, data: dict):
        """
        Transmits JSON data to all currently connected browser clients.
        """
        if not self.active_websockets:
            return

        disconnected = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            if ws in self.active_websockets:
                self.active_websockets.remove(ws)


# Global gateway coordinator instance
gateway = PerifericoGateway()


# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def get_health():
    """
    Aggregate health endpoint that returns:
      - Service process status (from watchdog .health_status.json)
      - Current emotional state (from config/emotions.json)
      - Memory tier storage usage (from memoria_activa/ size × config)
    """
    result = {
        "services": {},
        "emotion": None,
        "memory_tier": {
            "hot_usage_pct": 0.0,
            "hot_usage_gb": 0.0
        }
    }

    # 1. Read watchdog health status file
    health_path = os.path.join(PROJECT_ROOT, "config", ".health_status.json")
    try:
        if os.path.exists(health_path):
            with open(health_path, "r", encoding="utf-8") as f:
                health_data = json.load(f)
            result["services"] = health_data.get("services", {})
    except Exception as e:
        logger.error(f"Error reading health status: {e}")

    # 2. Read emotional state
    emotion_path = os.path.join(PROJECT_ROOT, "config", "emotions.json")
    try:
        if os.path.exists(emotion_path):
            with open(emotion_path, "r", encoding="utf-8") as f:
                result["emotion"] = json.load(f)
    except Exception as e:
        logger.error(f"Error reading emotions: {e}")

    # 3. Calculate hot memory tier disk usage
    memoria_path = os.path.join(PROJECT_ROOT, "memoria_activa")
    try:
        hot_gb = _get_dir_size_gb(memoria_path)
        result["memory_tier"]["hot_usage_gb"] = round(hot_gb, 4)

        # Read tiering config for max capacity
        tiering_path = os.path.join(PROJECT_ROOT, "config", "memory_tiering.yaml")
        max_gb = 100.0  # default fallback
        try:
            if os.path.exists(tiering_path):
                with open(tiering_path, "r", encoding="utf-8") as f:
                    tier_cfg = yaml.safe_load(f)
                max_gb = float(
                    tier_cfg.get("storage", {})
                    .get("ssd_hot", {})
                    .get("max_capacity_gb", 100)
                )
        except Exception:
            pass

        result["memory_tier"]["hot_usage_pct"] = (
            round(hot_gb / max_gb, 4) if max_gb > 0 else 0.0
        )
    except Exception as e:
        logger.error(f"Error calculating memory usage: {e}")

    return result


@app.get("/api/config")
async def get_config():
    """
    Returns current LLM Router YAML configuration as JSON.
    """
    config_path = os.path.join(PROJECT_ROOT, "config", "llm_router.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/config")
async def save_config(request: Request):
    """
    Accepts JSON containing new LLM model/api configs, writes it to
    llm_router.yaml, and publishes a reload_config command onto the
    system broker topic.
    """
    config_path = os.path.join(PROJECT_ROOT, "config", "llm_router.yaml")
    try:
        new_cfg = await request.json()
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(new_cfg, f, default_flow_style=False)

        # Publish reload event to broker system topic
        await gateway.publish_event("system", {"action": "reload_config", "timestamp": time.time()})
        return {"status": "success", "message": "Configuration saved and router reloaded."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/api/memoria")
async def get_memoria():
    """
    Connects to LanceDB, reads the memoria_fractal table and returns all stored
    memory nodes with text details and 3D spatial coordinates.
    """
    db_path = os.path.join(PROJECT_ROOT, "memoria_activa")
    if not os.path.exists(db_path):
        return []
    try:
        db = lancedb.connect(db_path)
        if "memoria_fractal" in db.list_tables():
            tbl = db.open_table("memoria_fractal")
            df = tbl.to_pandas()
            results = []
            for _, row in df.iterrows():
                results.append({
                    "id": row.get("id", ""),
                    "texto": row.get("texto", ""),
                    "x": float(row.get("x", 0.0)),
                    "y": float(row.get("y", 0.0)),
                    "z": float(row.get("z", 0.0)),
                    "timestamp": float(row.get("timestamp", 0.0))
                })
            return results
    except Exception as e:
        logger.error(f"Error reading memory for API: {e}")
    return []


@app.get("/models")
async def get_models_page():
    return FileResponse(os.path.join(GUI_DIR, "models.html"))


@app.get("/api/models")
async def get_models_list():
    registry_path = os.path.join(PROJECT_ROOT, "config", "model_registry.json")
    if not os.path.exists(registry_path):
        return []
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            models_data = json.load(f)
        return models_data
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/models")
async def save_new_model(request: Request):
    registry_path = os.path.join(PROJECT_ROOT, "config", "model_registry.json")
    try:
        new_model = await request.json()

        # Load existing
        models_data = []
        if os.path.exists(registry_path):
            with open(registry_path, "r", encoding="utf-8") as f:
                models_data = json.load(f)

        # Assign ID
        new_model["id"] = f"model-{int(time.time())}-{len(models_data)}"
        models_data.append(new_model)

        # Write back
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(models_data, f, indent=2, ensure_ascii=False)

        return {"status": "success", "message": "Model registered successfully in database."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# ---------------------------------------------------------------------------
# Phase 7: Credential management, dynamic model mapping, and module config
# ---------------------------------------------------------------------------

@app.get("/api/config/credenciales")
async def get_credenciales():
    """
    Reads credentials from .env file and returns them.
    Keys returned: OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, LMSTUDIO_API_KEY, TAVILY_API_KEY
    """
    try:
        from dotenv import dotenv_values
        env_path = os.path.join(PROJECT_ROOT, ".env")
        creds = {}
        if os.path.exists(env_path):
            env_vars = dotenv_values(env_path)
            keys_to_return = ["OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LMSTUDIO_API_KEY", "TAVILY_API_KEY"]
            for k in keys_to_return:
                creds[k] = env_vars.get(k, "")
        return {"status": "success", "credenciales": creds}
    except Exception as e:
        logger.error(f"Error reading credentials: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "mensaje": str(e)})

@app.post("/api/config/credenciales")
async def guardar_credenciales(request: Request):
    """
    Saves provider credentials (api_key, api_base) to the .env file
    using python-dotenv's set_key() for permanent persistence.
    """
    try:
        data = await request.json()
        proveedor = data.get("proveedor", "custom")
        api_key = data.get("api_key", "")
        api_base = data.get("api_base", "")

        env_path = os.path.join(PROJECT_ROOT, ".env")
        # Create .env if it doesn't exist
        if not os.path.exists(env_path):
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"# Vision OS — Environment Configuration\n")

        changes = []
        if api_key:
            key_name = f"{proveedor.upper()}_API_KEY"
            set_key(env_path, key_name, api_key)
            changes.append(key_name)
        if api_base:
            base_name = f"{proveedor.upper()}_API_BASE"
            set_key(env_path, base_name, api_base)
            changes.append(base_name)

        logger.info(f"Credenciales guardadas para '{proveedor}': {', '.join(changes)}")
        return {"status": "success", "message": f"Credenciales guardadas en .env: {', '.join(changes)}"}
    except Exception as e:
        logger.error(f"Error guardando credenciales: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/api/config/modelos")
async def get_config_modelos():
    """Returns the model configuration (strategies block) from llm_router.yaml."""
    config_path = os.path.join(PROJECT_ROOT, "config", "llm_router.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return {
            "status": "success",
            "routing_strategy": cfg.get("routing_strategy", "locales"),
            "roles": cfg.get("roles", {}),
            "strategies": cfg.get("strategies", {})
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/config/modelos")
async def save_config_modelos(request: Request):
    """Writes updated model config to llm_router.yaml and triggers hot reload."""
    config_path = os.path.join(PROJECT_ROOT, "config", "llm_router.yaml")
    try:
        updates = await request.json()

        # Read existing config
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        # Apply updates (merge strategies, roles, routing_strategy)
        if "routing_strategy" in updates:
            cfg["routing_strategy"] = updates["routing_strategy"]
        if "strategies" in updates:
            cfg["strategies"] = updates["strategies"]
        if "roles" in updates:
            cfg["roles"] = updates["roles"]

        # Write back
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False)

        # Publish reload event to broker
        await gateway.publish_event("system", {"action": "reload_config", "timestamp": time.time()})
        return {"status": "success", "message": "Model config updated and router reloaded."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})



@app.get("/api/config/modulos")
async def get_config_modulos():
    """Returns module configuration (hardware toggles, profiles, etc.)."""
    modulos_path = os.path.join(PROJECT_ROOT, "config", "modulos.yaml")
    defaults = {
        "oido": {"activo": True, "pausado": False},
        "vision": {"frecuencia_captura_seg": 5.0},
        "intriga": {"sensibilidad": 1},
        "perfil_nervioso": "equilibrado"
    }
    try:
        if os.path.exists(modulos_path):
            with open(modulos_path, "r", encoding="utf-8") as f:
                mod_cfg = yaml.safe_load(f)
            return {"status": "success", "config": mod_cfg}
        return {"status": "success", "config": defaults}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/config/modulos")
async def save_config_modulos(request: Request):
    """Saves module configuration to config/modulos.yaml."""
    modulos_path = os.path.join(PROJECT_ROOT, "config", "modulos.yaml")
    try:
        mod_cfg = await request.json()
        with open(modulos_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(mod_cfg, f, default_flow_style=False)
        return {"status": "success", "message": "Module configuration saved."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/api/config/microfonos")
async def list_microphones():
    """Lists detected PyAudio microphone input devices."""
    devices = []
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        try:
            for i in range(p.get_device_count()):
                try:
                    info = p.get_device_info_by_index(i)
                    if info.get('maxInputChannels', 0) > 0:
                        devices.append({
                            "index": i,
                            "name": info.get('name', f"Microphone {i}")
                        })
                except Exception:
                    pass
        finally:
            p.terminate()
        return {"status": "success", "devices": devices}
    except Exception as e:
        logger.warning(f"Failed to list microphones: {e}")
        return {"status": "error", "message": str(e), "devices": []}


@app.get("/api/config/altavoces")
async def list_speakers():
    """Lists detected PyAudio speaker output devices."""
    devices = []
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        try:
            for i in range(p.get_device_count()):
                try:
                    info = p.get_device_info_by_index(i)
                    if info.get('maxOutputChannels', 0) > 0:
                        devices.append({
                            "index": i,
                            "name": info.get('name', f"Speaker {i}")
                        })
                except Exception:
                    pass
        finally:
            p.terminate()
        return {"status": "success", "devices": devices}
    except Exception as e:
        logger.warning(f"Failed to list speakers: {e}")
        return {"status": "error", "message": str(e), "devices": []}


@app.get("/api/config/camaras")
async def list_cameras():
    """
    Detects available camera indices using cv2.VideoCapture with DirectShow on Windows.
    Checks indices from 0 to 3.
    """
    devices = []
    try:
        import cv2
        loop = asyncio.get_running_loop()
        def _check_cameras():
            cam_list = []
            for i in range(4):
                try:
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        cam_list.append({
                            "id": i,
                            "nombre": f"Cámara Windows/Móvil {i}"
                        })
                        cap.release()
                except Exception:
                    pass
            return cam_list
            
        devices = await loop.run_in_executor(None, _check_cameras)
        return {"status": "success", "devices": devices}
    except Exception as e:
        logger.warning(f"Failed to list cameras: {e}")
        return {"status": "error", "message": str(e), "devices": []}


@app.get("/api/config/hardware")
async def get_config_hardware():
    """Returns the content of config/hardware_interfaces.json."""
    hw_path = os.path.join(PROJECT_ROOT, "config", "hardware_interfaces.json")
    defaults = {
        "vision_activa": {
            "interval_seconds": 5,
            "monitor_index": 1,
            "modelo_vision": "local/qwen3-vl",
            "difference_threshold": 0.01,
            "camara_activa": False,
            "camara_index": 0,
            "camera_ip": ""
        },
        "oido_activo": {
            "input_device_index": None,
            "energy_threshold": 300,
            "dynamic_energy_threshold": True,
            "whisper_model": "tiny"
        },
        "habla_activa": {
            "output_device_index": None,
            "tts_engine": "edge-tts"
        }
    }
    try:
        if os.path.exists(hw_path):
            with open(hw_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # Ensure keys exist
            for key, val in defaults.items():
                if key not in cfg:
                    cfg[key] = val
                else:
                    for subkey, subval in val.items():
                        if subkey not in cfg[key]:
                            cfg[key][subkey] = subval
            return {"status": "success", "config": cfg}
        return {"status": "success", "config": defaults}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/config/hardware")
async def save_config_hardware(request: Request):
    """Saves hardware configuration to config/hardware_interfaces.json."""
    hw_path = os.path.join(PROJECT_ROOT, "config", "hardware_interfaces.json")
    try:
        cfg = await request.json()
        with open(hw_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        await gateway.publish_event("system", {"action": "reload_hardware_config", "timestamp": time.time()})
        return {"status": "success", "message": "Hardware configuration saved."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/api/config/arranque")
async def get_config_arranque():
    """Returns the content of config/arranque.yaml."""
    arr_path = os.path.join(PROJECT_ROOT, "config", "arranque.yaml")
    defaults = {
        "modos_mock": {
            "vision_parietal": False,
            "oido_parietal": True,
            "imaginacion_occipital": True,
            "ejecutor_izquierdo": True,
            "lancedb_manager": True,
            "protocolo_intriga": True,
            "habla_parietal": True
        }
    }
    try:
        if os.path.exists(arr_path):
            with open(arr_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            return {"status": "success", "config": cfg}
        return {"status": "success", "config": defaults}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/config/arranque")
async def save_config_arranque(request: Request):
    """Saves startup configuration to config/arranque.yaml."""
    arr_path = os.path.join(PROJECT_ROOT, "config", "arranque.yaml")
    try:
        cfg = await request.json()
        with open(arr_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False)
        await gateway.publish_event("system", {"action": "reload_arranque", "timestamp": time.time()})
        return {"status": "success", "message": "Startup configuration saved."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


def get_vision_model_details():
    try:
        yaml_path = os.path.join(PROJECT_ROOT, "config", "llm_router.yaml")
        with open(yaml_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        strategy = cfg.get("routing_strategy", "hibrido_api")
        model_cfg = cfg.get("strategies", {}).get(strategy, {}).get("esfuerzo_medio", {})
        model_name = model_cfg.get("model", "openrouter/google/gemini-2.5-flash:free")
        api_base = model_cfg.get("api_base")
        api_key_env = model_cfg.get("api_key")
        api_key = os.environ.get(api_key_env, api_key_env) if api_key_env else None
        return model_name, api_base, api_key
    except Exception:
        return "openrouter/google/gemini-2.5-flash:free", "https://openrouter.ai/api/v1", os.environ.get("OPENROUTER_API_KEY")


@app.post("/api/memoria/aprender")
async def api_memoria_aprender(file: UploadFile = File(...), description: str = Form(None)):
    """
    Multimodal learning port that ingests texts, audio or images, extracts/processes
    information and indexes it in LanceDB.
    """
    filename = file.filename
    content_type = file.content_type or ""
    logger.info(f"Learning API: Ingesting file '{filename}' of type '{content_type}'")

    # 1. Save upload to temp file
    suffix = os.path.splitext(filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        temp_file_path = tmp.name

    try:
        text_content = ""
        meta_source = "document"

        # 2. Ingestion MIME router
        # Images (png, jpg, jpeg, webp)
        if content_type.startswith("image/") or suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
            logger.info("MIME type: Image. Initiating vision analysis...")
            meta_source = "image"
            
            # Encode image in base64
            with open(temp_file_path, "rb") as img_f:
                img_b64 = base64.b64encode(img_f.read()).decode("utf-8")
                
            model_name, api_base, api_key = get_vision_model_details()
            
            prompt_text = "Describe esta imagen de forma extremadamente detallada para usarla como memoria contextual. Enumera los objetos, colores, texto visible y el tema central."
            if description:
                prompt_text += f" Contexto adicional proporcionado por el usuario: {description}"
                
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type or 'image/jpeg'};base64,{img_b64}"
                            }
                        }
                    ]
                }
            ]
            
            # Call vision LLM
            kwargs = {}
            if api_base:
                kwargs["api_base"] = api_base
            if api_key:
                kwargs["api_key"] = api_key
                
            logger.info(f"Calling vision model '{model_name}' to describe image...")
            response = await litellm.acompletion(
                model=model_name,
                messages=messages,
                timeout=30.0,
                **kwargs
            )
            text_content = response.choices[0].message.content
            logger.info("Successfully generated image description.")

        # Audio (mp3, wav, ogg, m4a, flac)
        elif content_type.startswith("audio/") or suffix.lower() in [".mp3", ".wav", ".ogg", ".m4a", ".flac"]:
            logger.info("MIME type: Audio. Initiating transcription...")
            meta_source = "audio"
            
            # Try faster-whisper first
            try:
                from faster_whisper import WhisperModel
                logger.info("Loading faster-whisper model...")
                model = WhisperModel("tiny", device="cpu", compute_type="int8")
                segments, info = model.transcribe(temp_file_path)
                text_content = " ".join([segment.text for segment in segments])
            except ImportError:
                # Fallback to speech_recognition
                logger.info("faster-whisper not installed. Falling back to speech_recognition...")
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                try:
                    with sr.AudioFile(temp_file_path) as src:
                        audio_data = recognizer.record(src)
                        text_content = recognizer.recognize_google(audio_data, language="es-ES")
                except Exception as audio_err:
                    logger.warning(f"Local speech recognition failed: {audio_err}. Generating fallback mock transcript.")
                    text_content = f"[Transcripción de audio fallida] Archivo: {filename}."
                    if description:
                        text_content += f" Descripción del audio: {description}"
            logger.info("Audio transcription completed.")

        # Documents (PDF, CSV, plain text)
        else:
            logger.info("MIME type: Document. Extracting text...")
            if suffix.lower() == ".pdf":
                try:
                    loader = PyPDFLoader(temp_file_path)
                    docs = loader.load()
                    text_content = "\n".join([doc.page_content for doc in docs])
                except Exception as pdf_err:
                    logger.error(f"Failed to load PDF: {pdf_err}")
                    raise pdf_err
            elif suffix.lower() == ".csv":
                try:
                    loader = CSVLoader(temp_file_path)
                    docs = loader.load()
                    text_content = "\n".join([doc.page_content for doc in docs])
                except Exception as csv_err:
                    logger.error(f"Failed to load CSV: {csv_err}")
                    raise csv_err
            else:
                try:
                    loader = TextLoader(temp_file_path, encoding="utf-8")
                    docs = loader.load()
                    text_content = "\n".join([doc.page_content for doc in docs])
                except Exception:
                    with open(temp_file_path, "r", encoding="utf-8", errors="ignore") as f:
                        text_content = f.read()
            logger.info(f"Extracted {len(text_content)} characters from document.")

        if not text_content.strip():
            raise ValueError("No text content could be extracted or generated from the uploaded file.")

        # 3. Publish to LanceDB via Broker Event
        metadata_payload = {
            "filename": filename,
            "mime_type": content_type,
            "source": meta_source,
            "timestamp": time.time()
        }
        if description:
            metadata_payload["user_description"] = description

        # Publish the guardar event
        publish_ok = await gateway.publish_event("canal.memoria", {
            "action": "guardar",
            "text": text_content,
            "coordenada_x": 0.0,
            "coordenada_y": 0.0,
            "temperatura_z": 100.0,  # Save to SSD Hot memory tier
            "escala_magnitud": "KB",
            "metadata": metadata_payload
        })

        if publish_ok:
            logger.info(f"Published learning document '{filename}' to LanceDB manager.")
            return {
                "status": "success",
                "message": f"File '{filename}' ingested successfully.",
                "type": meta_source,
                "extracted_content_preview": text_content[:200] + "..." if len(text_content) > 200 else text_content
            }
        else:
            return JSONResponse(status_code=500, content={
                "status": "error",
                "message": "Failed to publish learning document to LanceDB manager broker."
            })

    except Exception as e:
        logger.error(f"Error in multimodal learning endpoint: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass


@app.get("/api/modelos/lmstudio")
async def mapear_modelos_lmstudio():
    """
    Fetches models from LM Studio local server (localhost:1234)
    and returns detected models with their capabilities.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:1234/v1/models")
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("data", []):
                models.append({
                    "id": m.get("id", "unknown"),
                    "proveedor": "lmstudio",
                    "tipo": "local"
                })
            return {"status": "success", "modelos": models, "fuente": "lmstudio"}
    except httpx.ConnectError:
        return {"status": "offline", "modelos": [], "fuente": "lmstudio",
                "error": "LM Studio no está corriendo en localhost:1234"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "mensaje": str(e)})


@app.get("/api/modelos/ollama")
async def mapear_modelos_ollama():
    """
    Fetches models from local Ollama daemon (http://localhost:11434/api/tags)
    and returns detected models.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                models.append({
                    "id": m.get("name", "unknown"),
                    "proveedor": "ollama",
                    "tipo": "local"
                })
            return {"status": "success", "modelos": models, "fuente": "ollama"}
    except Exception as e:
        logger.warning(f"Failed to connect to Ollama: {e}")
        return {"status": "offline", "modelos": [], "fuente": "ollama",
                "error": "Ollama no está corriendo o no es accesible en localhost:11434"}


@app.post("/api/modelos/ollama/pull")
async def pull_ollama_model(request: Request):
    """
    Pulls a model from the Ollama registry.
    """
    try:
        data = await request.json()
        model_tag = data.get("modelo", "").strip()
        if not model_tag:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Falta el nombre del modelo."})
        
        model_name = f"ollama/{model_tag}"
        from cognitivo.gestor_modelos_locales import pull_model_if_missing
        
        # Run pull_model_if_missing in the event loop
        success = await pull_model_if_missing(model_name)
        if success:
            return {"status": "success", "message": f"Modelo {model_tag} descargado e instalado."}
            
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Falló la descarga del modelo {model_tag}."})
    except Exception as e:
        logger.error(f"Error pulling model: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/api/modelos/openrouter")
async def mapear_modelos_openrouter():
    """
    Fetches all models from OpenRouter API and separates them into
    gratuitos (free, pricing=0) and pago (paid).
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            data = resp.json()

            gratuitos = []
            pago = []
            for m in data.get("data", []):
                pricing = m.get("pricing", {})
                prompt_cost = float(pricing.get("prompt", 1))
                completion_cost = float(pricing.get("completion", 1))
                is_free = prompt_cost == 0 and completion_cost == 0

                entry = {
                    "id": m.get("id"),
                    "name": m.get("name", m.get("id")),
                    "context_length": m.get("context_length", 0),
                    "pricing": {"prompt": prompt_cost, "completion": completion_cost}
                }
                if is_free:
                    gratuitos.append(entry)
                else:
                    pago.append(entry)

            return {
                "status": "success",
                "gratuitos": gratuitos,
                "pago": pago,
                "total_gratis": len(gratuitos),
                "total_pago": len(pago)
            }
    except httpx.ConnectError:
        return {"status": "offline", "gratuitos": [], "pago": [],
                "error": "No se pudo conectar con OpenRouter"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "mensaje": str(e)})


@app.get("/api/archivos")
async def search_files(q: str = ""):
    query = q.lower().strip()
    if not query:
        return []

    results = []
    ignore_folders = {".git", ".venv", "node_modules", ".atl", ".opencode", "__pycache__"}

    count = 0
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in ignore_folders]
        for file in files:
            if query in file.lower():
                full_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(full_path)
                except Exception:
                    size = 0
                relative_path = os.path.relpath(full_path, PROJECT_ROOT)
                results.append({
                    "nombre": file,
                    "ruta": os.path.abspath(full_path),
                    "ruta_relativa": relative_path,
                    "tamaño_bytes": size,
                    "extension": os.path.splitext(file)[1].lower()
                })
                count += 1
                if count >= 30:
                    break
        if count >= 30:
            break

    return results


@app.post("/webhook/externo")
async def webhook_externo(request: Request):
    """
    Receives JSON body payloads from Telegram, GitHub or other third-party
    webhooks, and forwards them to 'canal.sensorial.periferico' in the broker.
    """
    try:
        data = await request.json()
    except Exception:
        data = {"detail": "Raw or unparsed content received"}

    logger.info(f"Webhook received: {data}")
    success = await gateway.publish_event("canal.sensorial.periferico", data)

    return {
        "status": "forwarded" if success else "failed",
        "payload_relayed": data
    }


@app.post("/upload_sensorial")
async def upload_sensorial(file: UploadFile = File(...)):
    """
    Receives sensory/multimedia files (Drag & Drop from GUI), saves them
    locally, and publishes the filepath to 'canal.sensorial.archivo_recibido'.
    """
    filename = file.filename
    # Prevent path traversal
    safe_filename = os.path.basename(filename)
    dest_path = os.path.join(TEMP_UPLOAD_DIR, safe_filename)

    logger.info(f"Uploading file: {safe_filename} to {dest_path}")
    try:
        with open(dest_path, "wb") as f:
            f.write(await file.read())

        # Publish event
        file_payload = {
            "ruta_local": os.path.abspath(dest_path),
            "nombre": safe_filename,
            "timestamp": time.time()
        }
        success = await gateway.publish_event("canal.sensorial.archivo_recibido", file_payload)

        return JSONResponse(status_code=200, content={
            "status": "success" if success else "broker_offline",
            "file_path": os.path.abspath(dest_path),
            "filename": safe_filename
        })
    except Exception as e:
        logger.error(f"Error handling file upload: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.websocket("/ws")
async def websocket_sensorial(websocket: WebSocket):
    """
    WebSocket endpoint connecting browser frontend clients (dashboard visual
    HUD). Listens for manual commands, HITL approvals, and Panic signals,
    and relays them to the broker.
    """
    await websocket.accept()
    gateway.active_websockets.append(websocket)
    logger.info(f"New dashboard client connected. Total clients: {len(gateway.active_websockets)}")

    try:
        while True:
            # Wait for text/JSON frames from the web app
            data_str = await websocket.receive_text()
            try:
                message = json.loads(data_str)
            except json.JSONDecodeError:
                logger.warning(f"Malformed WS payload: {data_str}")
                continue

            action = message.get("action")
            topic = message.get("topic")
            data = message.get("data", {})

            logger.info(f"WebSocket client message received. Action: {action}, Topic: {topic}")

            if action == "publish" and topic:
                # Forward publication request directly to Event Broker
                await gateway.publish_event(topic, data)
            elif action == "panic":
                # Max alert panic purge command
                logger.warning("🛑 PANIC STOP triggered from GUI Dashboard! Purging all queues.")
                purge_event = {
                    "action": "publish",
                    "topic": "system",
                    "data": {
                        "action": "purge",
                        "timestamp": time.time()
                    }
                }
                # Publish direct event to system topic
                await gateway.publish_event("system", purge_event["data"])

    except WebSocketDisconnect:
        logger.info("Dashboard client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket exception: {e}")
    finally:
        if websocket in gateway.active_websockets:
            gateway.active_websockets.remove(websocket)
        logger.info(f"Dashboard client cleaned up. Connected remaining: {len(gateway.active_websockets)}")


async def run_server():
    # 1. Start the broker connection daemon task
    asyncio.create_task(gateway.connect_to_broker_loop())

    # 2. Run Uvicorn Server directly in the running event loop
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=gateway.web_port,
        log_level="info",
        loop="asyncio"  # Force uvicorn to share the running asyncio loop
    )
    server = uvicorn.Server(config)
    logger.info(f"Starting Web API and WebSocket Gateway on http://127.0.0.1:{gateway.web_port}...")
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Sistema Periférico stopped.")
