import asyncio
import json
import logging
import os
import sys
import yaml
import litellm

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
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
            logger.info("Configuration loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load router config: {e}")
            self.config = {}

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
                with open(EFFORT_LEVELS_PATH, "r", encoding="utf-8") as f:
                    el_data = json.load(f)
                    effort_cfg = el_data.get(effort, {})
                    temp = effort_cfg.get("temperature", temp)
                    max_tokens = effort_cfg.get("max_tokens", max_tokens)
        except Exception as e:
            logger.warning(f"Failed to load effort levels config: {e}")

        # Load emotions and override temperature
        try:
            if os.path.exists(EMOTIONS_PATH):
                with open(EMOTIONS_PATH, "r", encoding="utf-8") as f:
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
            timeout_segundos = 60.0 if es_local else 15.0
            logger.info(f"Timeout configured as {timeout_segundos}s for model {model_name} (local={es_local})")

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
                return await self.call_llm(fallback, prompt, mock)
            else:
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

    async def run(self):
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

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
            # 1. Orchestrator stage: classify intention using low-effort model
            await self.publish_log(writer, "🤖 [Lóbulo Frontal] Petición recibida. Clasificando intención...")
            
            delegate = "chat_agent"
            recommended_effort = effort
            delegation_reason = "Conversación estándar"
            subprompt = prompt

            if not mock:
                classification_prompt = (
                    "Analiza el siguiente mensaje del usuario y clasifícalo para delegarlo al agente experto adecuado de Visión OS.\n"
                    f"Mensaje del usuario: \"{prompt}\"\n\n"
                    "Debes responder EXCLUSIVAMENTE con un objeto JSON válido con la siguiente estructura (sin markdown, bloques de código, ni texto adicional):\n"
                    "{\n"
                    "  \"delegate\": \"graph_agent\" | \"ingest_agent\" | \"peripheral_agent\" | \"chat_agent\",\n"
                    "  \"recommended_effort\": \"esfuerzo_bajo\" | \"esfuerzo_medio\" | \"esfuerzo_alto\",\n"
                    "  \"delegation_reason\": \"breve explicación en español de por qué elegís este agente\",\n"
                    "  \"subprompt\": \"el mensaje del usuario refinado o adaptado para el agente experto\"\n"
                    "}"
                )
                try:
                    # Run classification
                    classification_resp, _ = await self.call_llm("esfuerzo_bajo", classification_prompt, mock=False)
                    
                    # Clean markdown code blocks if any
                    clean_str = classification_resp.strip()
                    if clean_str.startswith("```json"):
                        clean_str = clean_str[7:]
                    if clean_str.endswith("```"):
                        clean_str = clean_str[:-3]
                    clean_str = clean_str.strip()

                    parsed = json.loads(clean_str)
                    delegate = parsed.get("delegate", "chat_agent")
                    recommended_effort = parsed.get("recommended_effort", effort)
                    delegation_reason = parsed.get("delegation_reason", "Conversación general")
                    subprompt = parsed.get("subprompt", prompt)
                except Exception as parse_err:
                    logger.warning(f"Orchestrator classification failed to parse: {parse_err}. Falling back to default chat_agent.")

            # Log delegation step to HUD console
            log_msg = f"📡 [Delegación] Intención: {delegation_reason} -> Derivando a [{delegate}] ({recommended_effort})"
            await self.publish_log(writer, log_msg)

            # 2. Expert agent processing
            expert_prompt = ""
            if delegate == "graph_agent":
                await self.publish_log(writer, f"🔍 [Agente de Grafo] Consultando LanceDB para buscar '{subprompt}'...")
                
                search_future = asyncio.get_running_loop().create_future()
                self.pending_searches[request_id] = search_future

                # Request semantic search
                search_msg = {
                    "action": "publish",
                    "topic": "canal.memoria",
                    "data": {
                        "action": "buscar",
                        "request_id": request_id,
                        "query": subprompt,
                        "top_n": 3
                    }
                }
                writer.write((json.dumps(search_msg) + "\n").encode("utf-8"))
                await writer.drain()

                # Await search response from LanceDBManager
                try:
                    results = await asyncio.wait_for(search_future, timeout=4.0)
                except asyncio.TimeoutError:
                    results = []
                    logger.warning("Timeout waiting for memory search.")

                if results:
                    formatted = "\n".join([
                        f"- Fichero: {r.get('metadata', {}).get('filename', 'desconocido')} (Distancia: {r.get('score', 1.0):.3f})\n  Excerpto: {r.get('text', '')}"
                        for r in results
                    ])
                    await self.publish_log(writer, f"✅ [Agente de Grafo] Encontradas {len(results)} memorias vectoriales relevantes.")
                else:
                    formatted = "No se encontraron memorias vectoriales coincidentes."
                    await self.publish_log(writer, "⚠️ [Agente de Grafo] No se obtuvieron coincidencias.")

                expert_prompt = (
                    "Eres el Agente de Grafo y Base de Datos Vectorial de Visión OS.\n"
                    "Tu especialidad es analizar los nodos de memoria y responder al usuario utilizando la información de la base de datos local.\n"
                    "Debes responder en español de manera atenta.\n\n"
                    f"Información recuperada de LanceDB:\n{formatted}\n\n"
                    f"Mensaje del usuario: {subprompt}\n"
                )

            elif delegate == "peripheral_agent":
                await self.publish_log(writer, "👁️ [Agente de Periféricos] Leyendo el estado del sistema...")
                system_context = (
                    "- Monitor activo: Monitor 1 (Principal)\n"
                    "- Captura de pantalla: Activa en Lóbulo Parietal (sentidos/vision_parietal.py)\n"
                    "- Modos de ruteo configurados: Locales (Ollama), Híbrido (API), Mensual (Suscripción)\n"
                    "- Ecosistema: Conectado a base de datos LanceDB (memoria_activa)\n"
                )
                expert_prompt = (
                    "Eres el Agente de Periféricos y Hardware de Visión OS.\n"
                    "Reportas sobre el estado del capturador de pantalla, ventanas activas y periféricos.\n"
                    "Responde en español basándote en este estado:\n\n"
                    f"{system_context}\n\n"
                    f"Mensaje del usuario: {subprompt}\n"
                )

            elif delegate == "ingest_agent":
                await self.publish_log(writer, "📥 [Agente de Ingestión] Iniciando asistente de importación...")
                expert_prompt = (
                    "Eres el Agente de Ingestión de Documentos de Visión OS.\n"
                    "Guías al usuario para subir, procesar e importar archivos o PDFs en el sistema.\n"
                    "Responde en español de forma instructiva y clara.\n\n"
                    f"Mensaje del usuario: {subprompt}\n"
                )

            else:  # chat_agent
                await self.publish_log(writer, "💬 [Agente Conversacional] Procesando respuesta general...")
                expert_prompt = (
                    "Eres el Agente Conversacional de Visión OS.\n"
                    "Conversas de forma amigable y ayudas con dudas generales o programación.\n"
                    "Responde en español cálido.\n\n"
                    f"Mensaje del usuario: {subprompt}\n"
                )

            # 3. Check for code/programming requests → Torre de Programación
            texto_usuario = subprompt or prompt
            palabras_clave = [
                "programa", "código", "codigo", "escribí", "hacé un",
                "función", "clase", "implement", "algoritmo", "script",
                "api rest", "endpoint", "microservicio"
            ]
            es_peticion_codigo = any(kw in texto_usuario.lower() for kw in palabras_clave)

            if es_peticion_codigo and not mock:
                await self.publish_log(writer, "🏢 [Torre de Programación] Derivando a agentes Arquitecto → Programador → QA...")
                try:
                    from cognitivo.distrito_agentes.torre_programacion import ejecutar_peticion_codigo
                    codigo_final = await ejecutar_peticion_codigo(texto_usuario)
                    response_text = codigo_final
                    model_used = "Torre de Programación (Arquitecto+Programador+QA)"
                except ImportError:
                    await self.publish_log(writer, "⚠️ LangGraph no disponible. Usando LLM directo.")
                    response_text, model_used = await self.call_llm(recommended_effort, expert_prompt, mock)
                except Exception as e:
                    await self.publish_log(writer, f"⚠️ Error en Torre de Programación: {e}. Usando LLM directo.")
                    response_text, model_used = await self.call_llm(recommended_effort, expert_prompt, mock)
            else:
                # 4. Call the specialized expert model (normal flow)
                response_text, model_used = await self.call_llm(recommended_effort, expert_prompt, mock)
            
            response_event = {
                "action": "publish",
                "topic": "canal.cognitivo.respuesta",
                "data": {
                    "request_id": request_id,
                    "response": response_text,
                    "model_used": f"{delegate} ({model_used})",
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
