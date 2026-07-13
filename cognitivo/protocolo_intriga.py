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
                        return f"Solución alternativa: Error de hardware en iGPU/AMD. Actualice drivers."
        except Exception as e:
            logger.error(f"Error during Tavily search: {e}")
            return f"Solución alternativa: Fallo de red. Instale ffmpeg y actualice drivers."

    async def process_context(self, context_str: str, writer):
        """
        Scans interpreted contexts for error flags and triggers the ticketing process.
        """
        if "ANOMALIA_DETECTADA:" not in context_str:
            return

        error_text = context_str.split("ANOMALIA_DETECTADA:", 1)[1].strip()
        
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
                "temperatura_z": 100.0,
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
            logger.info(f"Solution memory saved to LanceDB. Error ticket closed.")
            
            # Print success message in green
            print(f"\n\033[92m[TICKET CERRADO] Solución guardada con éxito en la memoria fractal:\033[0m")
            print(f"\033[96m{solution}\033[0m\n")

            self.active_error = None
        except Exception as e:
            logger.error(f"Failed to store solution in LanceDB: {e}")

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
