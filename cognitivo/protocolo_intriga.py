import asyncio
import json
import logging
import sys
import time

from cognitivo.propuestas_skills import is_valid_tool_code, save_proposal, validate_cli_name
from cognitivo.skills.websearch_tool import WebSearchEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] ProtocoloIntriga: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ProtocoloIntriga")

# First word of the answer to a research ticket, from voice or from the HUD ticket buttons.
APPROVAL_WORDS = {"si", "sí", "dale", "ok", "procede", "adelante", "yes"}
REJECTION_WORDS = {"no", "abortar", "aborta", "cancela", "cancelar"}


class ProtocoloIntriga:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000, is_mock: bool = False):
        self.host = host
        self.port = port
        self.is_mock = is_mock

        # State tracking
        self.active_error = None
        self.waiting_for_confirmation = False
        self.last_reported_error = None
        self.last_report_time = 0.0

    async def buscar_en_web(self, query: str) -> str | None:
        """
        Web search through the shared engine (DuckDuckGo, then Tavily). Returns the top results with their
        URLs, or None when nothing was found; it never makes up an answer.
        """
        response = await WebSearchEngine().buscar(query, max_results=5)
        if response.status != "success" or not response.results:
            logger.warning(f"Web search found nothing for '{query}': {response.error or response.status}")
            return None
        return "\n\n".join(f"{r.title}\n{r.url}\n{r.snippet}" for r in response.results)

    async def _publish(self, writer, topic: str, data: dict):
        try:
            writer.write((json.dumps({"action": "publish", "topic": topic, "data": data}) + "\n").encode("utf-8"))
            await writer.drain()
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")

    async def process_context(self, context_str: str, writer):
        """
        Scans interpreted contexts for error flags and triggers the ticketing process.
        """
        clean_context = context_str.strip()
        has_anomaly = False
        prefix_to_split = "ANOMALIA_DETECTADA:"

        # Check potential prefix matches at the start of the string
        if clean_context.startswith("ANOMALIA_DETECTADA:"):
            has_anomaly = True
            prefix_to_split = "ANOMALIA_DETECTADA:"
        elif clean_context.startswith("**ANOMALIA_DETECTADA:**"):
            has_anomaly = True
            prefix_to_split = "**ANOMALIA_DETECTADA:**"
        elif clean_context.startswith("### ANOMALIA_DETECTADA:"):
            has_anomaly = True
            prefix_to_split = "### ANOMALIA_DETECTADA:"
        elif clean_context.startswith("### **ANOMALIA_DETECTADA:**"):
            has_anomaly = True
            prefix_to_split = "### **ANOMALIA_DETECTADA:**"

        if not has_anomaly:
            return

        error_text = clean_context.split(prefix_to_split, 1)[1].strip()

        # Debounce/deduplicate consecutive identical error reports within 15 seconds
        current_time = time.time()
        if error_text == self.last_reported_error and (current_time - self.last_report_time) < 15.0:
            return

        self.last_reported_error = error_text
        self.last_report_time = current_time

        self.active_error = error_text
        # Researching sends the on-screen error text to external search engines, so ask first (HITL).
        self.waiting_for_confirmation = True
        logger.info(f"Anomalía detectada en pantalla: '{error_text}'. Esperando permiso para investigar.")

        await self._publish(
            writer,
            "canal.sistema.anuncios",
            {
                "mensaje": (
                    f"[PROTOCOLO INTRIGA] Detecté el error '{error_text}'. ¿Me das permiso para crear un ticket de "
                    "situación e investigar la solución en la web?"
                ),
                "error_original": error_text,
                "timestamp": current_time,
            },
        )

    async def handle_transcription(self, text: str, writer):
        """Answers to a pending research ticket ("sí, procede" / "no, abortar") from voice or the HUD ticket."""
        if not self.waiting_for_confirmation:
            return
        words = text.strip().lower().replace(",", " ").split()
        first = words[0] if words else ""
        if first in APPROVAL_WORDS:
            self.waiting_for_confirmation = False
            await self._iniciar_investigacion(writer)
        elif first in REJECTION_WORDS:
            self.waiting_for_confirmation = False
            logger.info(f"Investigación cancelada por el usuario: '{self.active_error}'")
            await self._publish(
                writer,
                "canal.sistema.anuncios",
                {
                    "mensaje": f"[PROTOCOLO INTRIGA] Investigación cancelada: '{self.active_error}'.",
                    "timestamp": time.time(),
                },
            )
            self.active_error = None

    async def _iniciar_investigacion(self, writer):
        """Ask the frontal lobe for a search query for the approved error ticket."""
        req_id = f"intriga-search-formulation-{int(time.time())}"
        await self._publish(
            writer,
            "canal.cognitivo.peticion",
            {
                "request_id": req_id,
                "prompt": (
                    f"Eres un investigador de IT. El usuario tuvo el error [{self.active_error}]. "
                    "Formula una consulta de búsqueda web altamente técnica para solucionar esto, "
                    "deduciendo e incluyendo posibles arquitecturas de hardware (gráficas integradas, AMD, Intel) "
                    "para abarcar las soluciones más probables. Responde solo con la consulta."
                ),
                "esfuerzo_requerido": "esfuerzo_medio",
            },
        )
        await self._publish(
            writer,
            "canal.sistema.anuncios",
            {"mensaje": f"[PROTOCOLO INTRIGA] Investigando: '{self.active_error}'...", "timestamp": time.time()},
        )
        logger.info(f"Dispatched search formulation request '{req_id}' to Lóbulo Frontal.")

    async def handle_llm_response(self, request_id: str, response_text: str, writer):
        """
        Executes web search using formulated query and stores solution in LanceDB.
        """
        if request_id.startswith("capacitacion-tool-"):
            await self._guardar_propuesta_herramienta(request_id, response_text, writer)
            return

        if not request_id.startswith("intriga-search-formulation-"):
            return

        logger.info(f"Search query formulated by Lóbulo Frontal: '{response_text}'")
        error = self.active_error
        self.active_error = None

        solution = await self.buscar_en_web(response_text)
        if solution is None:
            await self._publish(
                writer,
                "canal.sistema.anuncios",
                {
                    "mensaje": f"[PROTOCOLO INTRIGA] No encontré una solución en la web para '{error}'. Ticket cerrado.",
                    "timestamp": time.time(),
                },
            )
            return

        await self._publish(
            writer,
            "canal.memoria",
            {
                "action": "guardar",
                "text": f"Error: {error}\nBúsqueda: {response_text}\nFuentes encontradas:\n{solution}",
                "coordenada_x": 1.5,
                "coordenada_y": 2.5,
                "coordenada_z": 0.0,
                "coordenada_w": 100.0,
                "escala_magnitud": "KB",
                "metadata": {"tipo": "solucion_error", "error_original": error, "query_utilizada": response_text},
            },
        )
        await self._publish(
            writer,
            "canal.sistema.anuncios",
            {
                "mensaje": f"[PROTOCOLO INTRIGA] Guardé en memoria lo que encontré sobre '{error}'. Ticket cerrado.",
                "timestamp": time.time(),
            },
        )
        logger.info("Search results saved to memory. Error ticket closed.")

    async def _guardar_propuesta_herramienta(self, request_id: str, response_text: str, writer):
        """Quarantine LLM-written tool code for human review; it is never written into the package."""
        # request_id is "capacitacion-tool-<cli_name>-<timestamp>"; CLI names may contain hyphens.
        cli_part = request_id.removeprefix("capacitacion-tool-").rsplit("-", 1)[0]
        try:
            cli_name = validate_cli_name(cli_part)
        except ValueError as e:
            logger.warning(f"[Capacitación] Respuesta descartada: {e}")
            return

        clean_code = response_text.strip()
        if clean_code.startswith("```python"):
            clean_code = clean_code[9:]
        elif clean_code.startswith("```"):
            clean_code = clean_code[3:]
        if clean_code.endswith("```"):
            clean_code = clean_code[:-3]
        clean_code = clean_code.strip()

        if not is_valid_tool_code(clean_code):
            logger.warning(
                f"[Capacitación] El código generado para '{cli_name}' no define una herramienta @tool válida."
            )
            await self._publish(
                writer,
                "canal.sistema.anuncios",
                {
                    "mensaje": f"[CAPACITACIÓN] Se descartó la herramienta generada para '{cli_name}': no es código @tool válido.",
                    "timestamp": time.time(),
                },
            )
            return

        try:
            proposal = save_proposal(cli_name, clean_code)
        except OSError as e:
            logger.error(f"Failed to write tool proposal for {cli_name}: {e}")
            return
        logger.info(f"[Capacitación] Propuesta de herramienta para '{cli_name}' en cuarentena: {proposal}")

        await self._publish(
            writer,
            "canal.memoria",
            {
                "action": "guardar",
                "text": (
                    f"Propuesta de herramienta para la CLI '{cli_name}' pendiente de revisión humana en '{proposal}'. "
                    f"Código:\n{clean_code}"
                ),
                "coordenada_x": 2.0,
                "coordenada_y": 3.0,
                "coordenada_z": 0.0,
                "coordenada_w": 100.0,
                "escala_magnitud": "KB",
                "metadata": {"tipo": "propuesta_herramienta", "cli_name": cli_name, "timestamp": time.time()},
            },
        )
        await self._publish(
            writer,
            "canal.sistema.anuncios",
            {
                "mensaje": f"[CAPACITACIÓN] Herramienta propuesta para '{cli_name}'. Revísala en {proposal} antes de usarla.",
                "timestamp": time.time(),
            },
        )

    async def iniciar_protocolo_capacitacion(self, cli_name: str, writer):
        try:
            cli_name = validate_cli_name(cli_name)
        except ValueError as e:
            logger.warning(f"[Capacitación] Solicitud descartada: {e}")
            return
        logger.info(f"🎓 [Protocolo de Capacitación] Iniciando auto-capacitación para la CLI: '{cli_name}'")

        # 1. Search the web for CLI documentation and examples; without them the LLM would only guess.
        search_query = f"how to use {cli_name} cli python commands documentation examples"
        documentation = await self.buscar_en_web(search_query)
        if documentation is None:
            logger.warning(f"[Capacitación] Sin documentación para '{cli_name}'; capacitación pospuesta.")
            return

        # 2. Formulate LLM call to write the tool
        req_id = f"capacitacion-tool-{cli_name}-{int(time.time())}"

        prompt_write_tool = (
            "Eres el Protocolo de Capacitación Autónoma de Visión OS.\n"
            f"Hemos detectado que la herramienta CLI '{cli_name}' está instalada en el sistema local, pero carecemos de una herramienta en Python para controlarla.\n\n"
            f"Documentación e información técnica recopilada de la web:\n{documentation}\n\n"
            "Tu tarea es escribir un script de Python que exporte una herramienta de LangChain usando el decorador `@tool`.\n"
            "El script DEBE seguir exactamente estas directrices:\n"
            "1. Importar `from langchain_core.tools import tool`.\n"
            "2. Definir una función decorada con `@tool` que acepte parámetros, ejecute comandos del CLI de manera segura usando `subprocess`, y retorne el stdout/stderr como string.\n"
            "3. La función debe tener un docstring detallado explicando para qué sirve, para que el orquestador de LangGraph sepa cuándo invocarla.\n"
            "4. Responder ÚNICAMENTE con el código ejecutable de Python, sin bloques de código markdown ```python ni explicaciones adicionales. El código debe empezar directamente con los imports.\n"
            "Código de Python:"
        )

        llm_request = {
            "action": "publish",
            "topic": "canal.cognitivo.peticion",
            "data": {
                "request_id": req_id,
                "prompt": prompt_write_tool,
                "esfuerzo_requerido": "esfuerzo_medio",
            },
        }
        try:
            writer.write((json.dumps(llm_request) + "\n").encode("utf-8"))
            await writer.drain()
            logger.info(f"Dispatched tool generation request '{req_id}' to LLM Router.")
        except Exception as e:
            logger.error(f"Failed to publish tool writing request: {e}")

    async def run(self):
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                # Subscribe to required topics
                subscribe_msg = (
                    json.dumps(
                        {
                            "action": "subscribe",
                            "topics": [
                                "canal.sistema.contexto_actual",
                                "canal.sensorial.audio.transcripcion",
                                "canal.cognitivo.respuesta",
                                "canal.intriga",
                                "system",
                            ],
                        }
                    )
                    + "\n"
                )
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                while True:
                    line = await reader.readline()
                    if not line:
                        break

                    event = json.loads(line.decode("utf-8").strip())
                    topic = event.get("topic")
                    data = event.get("data", {})

                    if topic == "canal.sistema.contexto_actual":
                        contexto = data.get("contexto", "")
                        await self.process_context(contexto, writer)

                    elif topic == "canal.sensorial.audio.transcripcion":
                        transcription = data.get("transcripcion", "")
                        await self.handle_transcription(transcription, writer)

                    elif topic == "canal.intriga":
                        if data.get("modo") == "capacitacion":
                            cli_name = data.get("cli_name")
                            await self.iniciar_protocolo_capacitacion(cli_name, writer)

                    elif topic == "canal.cognitivo.respuesta":
                        req_id = data.get("request_id", "")
                        resp_text = data.get("response", "")
                        status = data.get("status", "")
                        if status == "success" and resp_text:
                            await self.handle_llm_response(req_id, resp_text, writer)

                    elif topic == "system" and data.get("command") == "shutdown":
                        logger.info("Shutdown command received. Exiting.")
                        return

            except Exception as e:
                logger.error(f"Connection lost or error in loop: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)


if __name__ == "__main__":
    mock_flag = "--mock" in sys.argv
    protocolo = ProtocoloIntriga(is_mock=mock_flag)
    try:
        asyncio.run(protocolo.run())
    except KeyboardInterrupt:
        logger.info("Protocolo de Intriga stopped.")
