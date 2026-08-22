import asyncio
import json
import logging
import os
import sys

import litellm
import yaml

# Add local path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from gestor_modelos_locales import pull_model_if_missing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] LobeFrontal: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("LLMRouter")

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "llm_router.yaml"
)
EFFORT_LEVELS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "effort_levels.json"
)
EMOTIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "emotions.json"
)

class LLMRouter:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        self.host = host
        self.port = port
        self.config = {}
        self.pending_searches = {}  # request_id -> asyncio.Future
        self.load_config()

    def load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
            logger.info("Configuration loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load router config: {e}")
        self.benchmarks = {}
        try:
            benchmark_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "model_benchmarks.json"
            )
            if os.path.exists(benchmark_path):
                with open(benchmark_path, encoding="utf-8") as f:
                    self.benchmarks = json.load(f)
                logger.info(f"Loaded {len(self.benchmarks)} model benchmarks.")
        except Exception as e:
            logger.warning(f"Could not load model benchmarks: {e}")

    def get_model_config(self, effort: str) -> dict:
        strategy = self.config.get("routing_strategy")
        strategies = self.config.get("strategies", {})
        if strategy and strategy in strategies:
            logger.info(f"Routing using strategy: '{strategy}'")
            return strategies[strategy].get(effort, {})

        # Fallback to old flat models block if strategy is missing
        models_cfg = self.config.get("models", {})
        return models_cfg.get(effort, {})

    async def call_llm(self, effort: str, prompt: str, mock: bool = False) -> tuple[str, str]:
        """
        Calls the model for the given effort level. Falls back recursively if it fails.
        Returns: (response_text, model_name_used)
        """
        model_cfg = self.get_model_config(effort)
        if not model_cfg:
            raise ValueError(f"No configuration found for effort level: {effort}")

        model_name = model_cfg.get("model")
        fallback = model_cfg.get("fallback")

        # Load effort levels default parameters
        temp = 0.5
        max_tokens = 512
        try:
            if os.path.exists(EFFORT_LEVELS_PATH):
                with open(EFFORT_LEVELS_PATH, encoding="utf-8") as f:
                    el_data = json.load(f)
                    effort_cfg = el_data.get(effort, {})
                    temp = effort_cfg.get("temperature", temp)
                    max_tokens = effort_cfg.get("max_tokens", max_tokens)
        except Exception as e:
            logger.warning(f"Failed to load effort levels config: {e}")

        # Load emotions and override temperature
        try:
            if os.path.exists(EMOTIONS_PATH):
                with open(EMOTIONS_PATH, encoding="utf-8") as f:
                    em_data = json.load(f)
                    estado = em_data.get("estado", "neutral").lower()
                    if estado in ["intriga", "creativo"]:
                        temp = 0.8
                        logger.info(f"Emotional override: state '{estado}' forced temperature to 0.8")
                    elif estado == "lógico":
                        temp = 0.0
                        logger.info(f"Emotional override: state '{estado}' forced temperature to 0.0")
        except Exception as e:
            logger.warning(f"Failed to load emotions config: {e}")

        if mock:
            logger.info(f"[MOCK] Simulating completion for model {model_name} at effort '{effort}' (Temp: {temp}, MaxTokens: {max_tokens})")
            return f"Mock response for prompt: '{prompt}' using {model_name} (temperature={temp})", model_name

        # Ensure local model is downloaded if it is an Ollama model
        if model_name.startswith("ollama/"):
            pulled_ok = await pull_model_if_missing(model_name, mock=False)
            if not pulled_ok:
                logger.warning(f"Failed to verify local model '{model_name}' presence.")

        api_base = model_cfg.get("api_base")
        api_key_env = model_cfg.get("api_key")
        api_key = os.environ.get(api_key_env, api_key_env) if api_key_env else None

        logger.info(f"Attempting LLM call using model: {model_name} (Effort: {effort}, Temp: {temp}, MaxTokens: {max_tokens})")

        try:
            # Configure API base if provided (e.g. for LM Studio local models)
            kwargs = {}
            if api_base:
                kwargs["api_base"] = api_base
            if api_key:
                kwargs["api_key"] = api_key

            # Detect if model is local (Ollama or LM Studio) for generous timeout
            es_local = (
                model_name.startswith("ollama/") or
                (api_base and any(h in (api_base or "").lower() for h in ["localhost:11434", "localhost:1234", "127.0.0.1:11434", "127.0.0.1:1234"]))
            )

            timeout_segundos = 30.0
            if es_local:
                # Resolve base model name (without 'ollama/' prefix if saved that way)
                base_model = model_name[7:] if model_name.startswith("ollama/") else model_name
                # Check if we have a measured benchmark for this model
                benchmark_data = self.benchmarks.get(base_model) or self.benchmarks.get(model_name)
                if benchmark_data and benchmark_data.get("status") == "success":
                    measured_time = float(benchmark_data.get("time_seconds", 30.0))
                    # Allow 2.5x the measured benchmark time as timeout buffer, minimum 45 seconds
                    timeout_segundos = max(measured_time * 2.5, 45.0)
                    logger.info(f"Using dynamic benchmarked timeout: {timeout_segundos:.2f}s for local model {model_name} (measured={measured_time:.2f}s)")
                else:
                    timeout_segundos = 300.0  # Default generous timeout for unbenchmarked local models
                    logger.info(f"No benchmark found for local model {model_name}. Defaulting to {timeout_segundos}s.")
            else:
                logger.info(f"Timeout configured as {timeout_segundos}s for cloud model {model_name}.")

            response = await litellm.acompletion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout_segundos,
                temperature=temp,
                max_tokens=max_tokens,
                **kwargs
            )
            response_text = response.choices[0].message.content
            return response_text, model_name

        except Exception as e:
            logger.warning(f"Failed LLM call for model {model_name}: {e}")
            if fallback:
                logger.info(f"Falling back from '{effort}' to '{fallback}'...")
                try:
                    return await self.call_llm(fallback, prompt, mock)
                except Exception as fb_err:
                    logger.warning(f"Fallback '{fallback}' also failed: {fb_err}")

            # If the strategy/model call failed completely, attempt to fall back to OpenRouter API
            if "openrouter" not in model_name.lower():
                logger.warning("Local LLM call failed. Attempting global safety fallback to OpenRouter API...")
                or_key = os.environ.get("OPENROUTER_API_KEY")
                if or_key:
                    try:
                        logger.info("Calling OpenRouter fallback: google/gemini-2.5-flash:free")
                        response = await litellm.acompletion(
                            model="openrouter/google/gemini-2.5-flash:free",
                            messages=[{"role": "user", "content": prompt}],
                            timeout=20.0,
                            temperature=temp,
                            max_tokens=max_tokens,
                            api_base="https://openrouter.ai/api/v1",
                            api_key=or_key
                        )
                        response_text = response.choices[0].message.content
                        logger.info("Successfully recovered using OpenRouter fallback!")
                        return response_text, "openrouter/google/gemini-2.5-flash:free"
                    except Exception as or_err:
                        logger.error(f"OpenRouter fallback also failed: {or_err}")
                else:
                    logger.warning("OPENROUTER_API_KEY not found in environment. Cannot perform OpenRouter fallback.")

            raise e

    async def publish_log(self, writer, message: str):
        event = {
            "action": "publish",
            "topic": "canal.sistema.contexto_actual",
            "data": {
                "contexto": message
            }
        }
        try:
            writer.write((json.dumps(event) + "\n").encode("utf-8"))
            await writer.drain()
        except Exception as e:
            logger.error(f"Failed to publish log: {e}")

    async def perform_memory_search(self, request_id: str, query: str, emotion_filter: str = "neutral") -> list:
        """
        Publishes a search request to the LanceDB manager and awaits the response.
        """
        if not hasattr(self, 'active_writer') or not self.active_writer:
            logger.warning("No active broker connection for memory search.")
            return []

        search_future = asyncio.get_running_loop().create_future()
        self.pending_searches[request_id] = search_future

        search_msg = {
            "action": "publish",
            "topic": "canal.memoria",
            "data": {
                "action": "buscar",
                "request_id": request_id,
                "query": query,
                "top_n": 3,
                "emotion_filter": emotion_filter
            }
        }
        try:
            self.active_writer.write((json.dumps(search_msg) + "\n").encode("utf-8"))
            await self.active_writer.drain()
            results = await asyncio.wait_for(search_future, timeout=4.0)
            return results
        except Exception as e:
            logger.error(f"Memory search error: {e}")
            return []

    async def run(self):
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")
                self.active_writer = writer

                # Subscribe to relevant topics including memory responses
                subscribe_msg = json.dumps({
                    "action": "subscribe",
                    "topics": ["canal.cognitivo.peticion", "canal.memoria.respuesta", "system"]
                }) + "\n"
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                while True:
                    line = await reader.readline()
                    if not line:
                        logger.warning("Broker closed connection.")
                        break

                    try:
                        event = json.loads(line.decode("utf-8").strip())
                    except json.JSONDecodeError:
                        continue

                    topic = event.get("topic")
                    data = event.get("data", {})

                    if topic == "system" and data.get("action") == "reload_config":
                        logger.info("System configuration reload signal received. Reloading router configuration.")
                        self.load_config()
                        continue

                    if topic == "system" and data.get("action") == "purge":
                        logger.warning("System purge signal received. Resetting state.")
                        continue

                    if topic == "canal.memoria.respuesta":
                        req_id = data.get("request_id")
                        if req_id in self.pending_searches:
                            future = self.pending_searches.pop(req_id)
                            if not future.done():
                                future.set_result(data.get("results", []))
                        continue

                    if topic == "canal.cognitivo.peticion":
                        request_id = data.get("request_id")
                        prompt = data.get("prompt")
                        effort = data.get("esfuerzo_requerido", "esfuerzo_bajo")
                        mock = data.get("mock", False)

                        if not request_id or not prompt:
                            logger.error("Received malformed request event.")
                            continue

                        # Process prompt asynchronously to not block event loop
                        asyncio.create_task(
                            self.process_request(writer, request_id, prompt, effort, mock)
                        )

            except Exception as e:
                logger.error(f"Error in LLM Router loop: {e}. Retrying connection in 5 seconds...")
                await asyncio.sleep(5)

    async def process_request(self, writer, request_id: str, prompt: str, effort: str, mock: bool):
        try:
            await self.publish_log(writer, "🤖 [Lóbulo Frontal] Procesando petición en Tren de Información (Grafo)...")

            # Execute StateGraph from orquestador_graph
            from orquestador_graph import ejecutar_orquestador_graph
            response_text = await ejecutar_orquestador_graph(prompt, request_id, mock)

            response_event = {
                "action": "publish",
                "topic": "canal.cognitivo.respuesta",
                "data": {
                    "request_id": request_id,
                    "response": response_text,
                    "model_used": "LangGraph StateGraph (Orquestador)",
                    "status": "success"
                }
            }
        except Exception as e:
            logger.error(f"All LLM attempts failed for request {request_id}: {e}")
            response_event = {
                "action": "publish",
                "topic": "canal.cognitivo.respuesta",
                "data": {
                    "request_id": request_id,
                    "error": str(e),
                    "status": "failed"
                }
            }

        try:
            payload = json.dumps(response_event) + "\n"
            writer.write(payload.encode("utf-8"))
            await writer.drain()
        except Exception as e:
            logger.error(f"Failed to publish response to broker: {e}")

# ---------------------------------------------------------------------------
# Helper function: enrutar_peticion — llama al LLM sin instanciar el router
# ---------------------------------------------------------------------------
_global_router: LLMRouter | None = None

async def enrutar_peticion(prompt: str, esfuerzo: str = "esfuerzo_bajo", mock: bool = False) -> str:
    """
    Función módulo-level para llamar al LLM desde cualquier agente.

    Args:
        prompt: El texto a enviar al modelo.
        esfuerzo: "esfuerzo_bajo", "esfuerzo_medio", o "esfuerzo_alto".
        mock: Si True, devuelve una respuesta simulada.

    Returns:
        El texto de respuesta del modelo.
    """
    global _global_router
    if _global_router is None:
        _global_router = LLMRouter()
    try:
        respuesta, modelo = await _global_router.call_llm(esfuerzo, prompt, mock=mock)
        return respuesta
    except Exception as e:
        logger.error(f"enrutar_peticion falló: {e}")
        return f"⚠️ Error al enrutar la petición: {e}"


if __name__ == "__main__":
    router = LLMRouter()
    try:
        asyncio.run(router.run())
    except KeyboardInterrupt:
        logger.info("Lóbulo Frontal (LLM Router) stopped.")
