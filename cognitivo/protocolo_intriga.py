import asyncio
import json
import logging
import os
import sys
import time

import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] ProtocoloIntriga: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ProtocoloIntriga")


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

    async def call_tavily_search(self, query: str) -> str:
        """
        Queries Tavily Search API. If no key is set or call fails, falls back to a simulated solution.
        """
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            logger.warning("TAVILY_API_KEY not found in environment. Simulating web search solution.")
            await asyncio.sleep(2.0)
            return (
                f"Solución Simulada para '{query}': "
                "Para solucionar fallos en iGPU Radeon o dGPU NVIDIA RTX 5060 Ti con codificadores de pantalla, "
                "actualice los controladores gráficos y reinstale FFMPEG de forma limpia en Windows."
            )

        logger.info(f"Executing Tavily web search for query: '{query}'...")
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.tavily.com/search"
                payload = {
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True
                }
                async with session.post(url, json=payload, timeout=8.0) as resp:
                    if resp.status == 200:
                        res_data = await resp.json()
                        answer = res_data.get("answer")
                        if answer:
                            return answer
                        results = res_data.get("results", [])
                        if results:
                            return results[0].get("content", "No information found.")
                        return "Búsqueda web completada sin resultados."
                    else:
                        logger.warning(f"Tavily returned HTTP {resp.status}. Falling back to simulation.")
                        return "Solución alternativa: Error de hardware en iGPU/AMD. Actualice drivers."
        except Exception as e:
            logger.error(f"Error during Tavily search: {e}")
            return "Solución alternativa: Fallo de red. Instale ffmpeg y actualice drivers."

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
        self.waiting_for_confirmation = False

        logger.info(f"Anomalía detectada en pantalla: '{error_text}'")

        # Print a highlighted message for the developer
        print(f"\n\033[93m[ALERTA DE INTRIGA] Error detectado: '{error_text}'\033[0m")
        print("\033[92mGenerando ticket de situación e iniciando investigación automática en la web...\033[0m\n")

        # Formulate query request to LLM Router (Lóbulo Frontal)
        req_id = f"intriga-search-formulation-{int(time.time())}"
        llm_request = {
            "action": "publish",
            "topic": "canal.cognitivo.peticion",
            "data": {
                "request_id": req_id,
                "prompt": (
                    f"Eres un investigador de IT. El usuario tuvo el error [{self.active_error}]. "
                    "Formula una consulta de búsqueda web altamente técnica para solucionar esto, "
                    "deduciendo e incluyendo posibles arquitecturas de hardware (gráficas integradas, AMD, Intel) "
                    "para abarcar las soluciones más probables."
                ),
                "esfuerzo_requerido": "esfuerzo_medio",
                "mock": self.is_mock
            }
        }
        try:
            writer.write((json.dumps(llm_request) + "\n").encode("utf-8"))
            await writer.drain()
            logger.info(f"Dispatched search formulation request '{req_id}' to Lóbulo Frontal.")
        except Exception as e:
            logger.error(f"Failed to request search formulation: {e}")

        # Publish alert event to the broker
        payload = {
            "action": "publish",
            "topic": "canal.sistema.anuncios",
            "data": {
                "mensaje": f"[PROTOCOLO INTRIGA] Error detectado: '{error_text}'. Generando ticket e iniciando investigación...",
                "error_original": error_text,
                "timestamp": current_time
            }
        }
        try:
            writer.write((json.dumps(payload) + "\n").encode("utf-8"))
            await writer.drain()
        except Exception as e:
            logger.error(f"Failed to publish anomaly alert: {e}")

    async def handle_transcription(self, text: str, writer):
        """
        Processes voice/text transcription events. Auto-ticketing is active, so this is a no-op.
        """
        pass

    async def handle_llm_response(self, request_id: str, response_text: str, writer):
        """
        Executes web search using formulated query and stores solution in LanceDB.
        """
        if request_id.startswith("capacitacion-tool-"):
            parts = request_id.split("-")
            cli_name = parts[2]
            clean_code = response_text.strip()
            if clean_code.startswith("```python"):
                clean_code = clean_code[9:]
            elif clean_code.startswith("```"):
                clean_code = clean_code[3:]
            if clean_code.endswith("```"):
                clean_code = clean_code[:-3]
            clean_code = clean_code.strip()

            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            skills_dir = os.path.join(project_root, "cognitivo", "skills")
            os.makedirs(skills_dir, exist_ok=True)
            tool_path = os.path.join(skills_dir, f"{cli_name}_tool.py")

            try:
                with open(tool_path, "w", encoding="utf-8") as f:
                    f.write(clean_code)
                logger.info(f"🎉 [Capacitación] Nueva herramienta guardada físicamente en: {tool_path}")

                save_payload = {
                    "action": "publish",
                    "topic": "canal.memoria",
                    "data": {
                        "action": "guardar",
                        "text": f"Aprendí a usar la CLI '{cli_name}'. Se creó y registró la herramienta en '{tool_path}'. Código:\n{clean_code}",
                        "coordenada_x": 2.0,
                        "coordenada_y": 3.0,
                        "coordenada_z": 0.0,
                        "coordenada_w": 100.0,
                        "escala_magnitud": "KB",
                        "metadata": {
                            "tipo": "auto_capacitacion",
                            "cli_name": cli_name,
                            "timestamp": time.time()
                        }
                    }
                }
                writer.write((json.dumps(save_payload) + "\n").encode("utf-8"))
                await writer.drain()
                logger.info(f"Learned tool index saved to LanceDB for {cli_name}.")
                print(f"\n\033[92m[AUTO-CAPACITACIÓN COMPLETADA] Visión aprendió a controlar la CLI '{cli_name}' y registró su tool.\033[0m\n")
            except Exception as e:
                logger.error(f"Failed to write generated skill file: {e}")
            return

        if not request_id.startswith("intriga-search-formulation-"):
            return

        logger.info(f"Search query formulated by Lóbulo Frontal: '{response_text}'")

        # 1. Run web search
        solution = await self.call_tavily_search(response_text)
        logger.info("Search solution compiled successfully.")

        # 2. Save solution to LanceDB (Lóbulo Temporal)
        save_payload = {
            "action": "publish",
            "topic": "canal.memoria",
            "data": {
                "action": "guardar",
                "text": f"Error: {self.active_error}\nBúsqueda: {response_text}\nSolución: {solution}",
                "coordenada_x": 1.5,
                "coordenada_y": 2.5,
                "coordenada_z": 0.0,
                "coordenada_w": 100.0,
                "escala_magnitud": "KB",
                "metadata": {
                    "tipo": "solucion_error",
                    "error_original": self.active_error,
                    "query_utilizada": response_text
                }
            }
        }
        try:
            writer.write((json.dumps(save_payload) + "\n").encode("utf-8"))
            await writer.drain()
            logger.info("Solution memory saved to LanceDB. Error ticket closed.")

            # Print success message in green
            print("\n\033[92m[TICKET CERRADO] Solución guardada con éxito en la memoria fractal:\033[0m")
            print(f"\033[96m{solution}\033[0m\n")

            self.active_error = None
        except Exception as e:
            logger.error(f"Failed to store solution in LanceDB: {e}")

    async def iniciar_protocolo_capacitacion(self, cli_name: str, writer):
        logger.info(f"🎓 [Protocolo de Capacitación] Iniciando auto-capacitación para la CLI: '{cli_name}'")

        # 1. Search Tavily for CLI documentation and examples
        search_query = f"how to use {cli_name} cli python commands documentation examples"
        logger.info(f"Querying Tavily for '{cli_name}' documentation...")
        documentation = await self.call_tavily_search(search_query)

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
                "mock": self.is_mock
            }
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
                subscribe_msg = json.dumps({
                    "action": "subscribe",
                    "topics": [
                        "canal.sistema.contexto_actual",
                        "canal.sensorial.audio.transcripcion",
                        "canal.cognitivo.respuesta",
                        "canal.intriga",
                        "system"
                    ]
                }) + "\n"
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
