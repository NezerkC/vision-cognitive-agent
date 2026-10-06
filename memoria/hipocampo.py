import asyncio
import json
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Hipocampo: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Hipocampo")


class Hipocampo:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        self.host = host
        self.port = port
        # Keep track of active requests to pair task_id with summarization response
        self.pending_tasks: dict[str, str] = {}

    def parse_tags_from_summary(self, summary_text: str) -> list[str]:
        """
        Heuristic to extract comma-separated tags from the summary output.
        """
        tags = []
        lines = summary_text.split("\n")
        for line in lines:
            if "tags:" in line.lower():
                tag_part = line.lower().split("tags:")[1]
                tags = [t.strip() for t in tag_part.split(",") if t.strip()]
                break
        return tags

    async def run(self):
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                # Subscribe to task completion and LLM responses
                subscribe_msg = (
                    json.dumps(
                        {
                            "action": "subscribe",
                            "topics": ["canal.sistema.fin_tarea", "canal.cognitivo.respuesta", "system"],
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

                    try:
                        event = json.loads(line.decode("utf-8").strip())
                    except json.JSONDecodeError:
                        continue

                    topic = event.get("topic")
                    data = event.get("data", {})

                    if topic == "system" and data.get("action") == "purge":
                        logger.warning("System purge signal received. Resetting pending summarization mappings.")
                        self.pending_tasks.clear()
                        continue

                    if topic == "canal.sistema.fin_tarea":
                        task_id = data.get("task_id")
                        history = data.get("history", [])
                        mock = data.get("mock", False)

                        if not task_id or not history:
                            logger.error("Received malformed fin_tarea event.")
                            continue

                        # Extract last 20 messages for consolidation
                        last_20 = history[-20:]
                        conversation_block = "\n".join(last_20)

                        logger.info(
                            f"Consolidating memory for task: {task_id}. Length of history: {len(last_20)} lines."
                        )

                        request_id = f"hipo-{task_id}"
                        self.pending_tasks[request_id] = task_id

                        # Prompt for Lobe Frontal
                        prompt = (
                            f"Resumí los siguientes mensajes de conversación en exactamente 3 viñetas (bullet points) clave "
                            f"y 5 tags representativos separados por comas. Mantén el formato estricto:\n\n"
                            f"[HISTORIAL DE CONVERSACIÓN]\n{conversation_block}\n\n"
                            f"Formato:\n"
                            f"- Viñeta 1\n"
                            f"- Viñeta 2\n"
                            f"- Viñeta 3\n"
                            f"Tags: tag1, tag2, tag3, tag4, tag5"
                        )

                        # Publish summarization request (goes to Amígdala -> LLM Router)
                        summarize_request = {
                            "action": "publish",
                            "topic": "canal.cognitivo.entrada",
                            "data": {
                                "request_id": request_id,
                                "prompt": prompt,
                                "esfuerzo_requerido": "esfuerzo_bajo",
                                "mock": mock,
                            },
                        }
                        writer.write((json.dumps(summarize_request) + "\n").encode("utf-8"))
                        await writer.drain()

                    elif topic == "canal.cognitivo.respuesta":
                        request_id = data.get("request_id", "")
                        if request_id.startswith("hipo-"):
                            task_id = self.pending_tasks.pop(request_id, None)
                            if not task_id:
                                continue

                            response_text = data.get("response", "")
                            status = data.get("status", "")

                            if status != "success" or not response_text:
                                logger.error(
                                    f"Summarization failed for request {request_id}. Memory consolidation aborted."
                                )
                                continue

                            logger.info(f"Consolidated summary received for task {task_id}.")

                            tags = self.parse_tags_from_summary(response_text)

                            # Publish memory storage command (Lóbulo Temporal)
                            save_event = {
                                "action": "publish",
                                "topic": "canal.memoria",
                                "data": {
                                    "action": "guardar",
                                    "text": response_text,
                                    "coordenada_x": 1.0,
                                    "coordenada_y": 1.0,
                                    "temperatura_z": 100.0,  # Hot tier
                                    "escala_magnitud": "KB",
                                    "metadata": {"task_id": task_id, "tags": tags, "source": "hipocampo_summary"},
                                },
                            }
                            writer.write((json.dumps(save_event) + "\n").encode("utf-8"))
                            await writer.drain()
                            logger.info(f"Published consolidated memory save event for task {task_id}.")

            except Exception as e:
                logger.error(f"Error in Hipocampo loop: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)


if __name__ == "__main__":
    hipocampo = Hipocampo()
    try:
        asyncio.run(hipocampo.run())
    except KeyboardInterrupt:
        logger.info("Hipocampo stopped.")
