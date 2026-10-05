import asyncio
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] TestPhase3: %(message)s")
logger = logging.getLogger("TestPhase3")


async def test_memory_pipeline():
    logger.info("Connecting to event broker...")
    reader, writer = await asyncio.open_connection("127.0.0.1", 5000)

    # Subscribe to memory and search response topics
    subscribe_msg = (
        json.dumps(
            {"action": "subscribe", "topics": ["canal.memoria", "canal.memoria.respuesta", "canal.memoria.error"]}
        )
        + "\n"
    )
    writer.write(subscribe_msg.encode("utf-8"))
    await writer.drain()
    logger.info("Subscribed to memory topics.")

    # Sleep to ensure all modules are registered
    await asyncio.sleep(1.5)

    # -------------------------------------------------------------
    # CASE 1: Trigger task completion (will kickstart Hipocampo summary)
    # -------------------------------------------------------------
    task_id = "task-integration-777"
    mock_history = [f"user: message number {i}" if i % 2 == 0 else f"agent: response number {i}" for i in range(20)]

    task_completion_event = {
        "action": "publish",
        "topic": "canal.sistema.fin_tarea",
        "data": {
            "task_id": task_id,
            "history": mock_history,
            "mock": True,  # Enable mock LLM completion
        },
    }

    logger.info(f"Publishing fin_tarea event for {task_id}...")
    writer.write((json.dumps(task_completion_event) + "\n").encode("utf-8"))
    await writer.drain()

    # Wait for the Hipocampo to request a summary, the LLM router to finish,
    # and the Hipocampo to issue a 'guardar' event on 'canal.memoria'.
    guardar_captured = False
    try:
        # We listen for the 'guardar' command being sent by Hipocampo
        for _ in range(5):
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not line:
                break

            event = json.loads(line.decode("utf-8").strip())
            topic = event.get("topic")
            data = event.get("data", {})
            logger.info(f"Test client read event on '{topic}': {data}")

            if topic == "canal.memoria" and data.get("action") == "guardar":
                metadata = data.get("metadata", {})
                if metadata.get("task_id") == task_id:
                    logger.info("VERIFICATION PASS: Hipocampo captured task end and triggered a memory guardar event.")
                    guardar_captured = True
                    break
    except asyncio.TimeoutError:
        logger.error("Timeout waiting for memory guardar event.")

    if not guardar_captured:
        logger.error("VERIFICATION FAILED: Guardar event not captured. Aborting search test.")
        writer.close()
        await writer.wait_closed()
        return

    # Sleep briefly to ensure LanceDB finishes writing
    await asyncio.sleep(2.0)

    # -------------------------------------------------------------
    # CASE 2: Semantic Search Query
    # -------------------------------------------------------------
    search_request_id = "search-req-999"
    search_event = {
        "action": "publish",
        "topic": "canal.memoria",
        "data": {"action": "buscar", "query": "Mock response for prompt", "top_n": 2, "request_id": search_request_id},
    }

    logger.info("Publishing semantic search query to LanceDB manager...")
    writer.write((json.dumps(search_event) + "\n").encode("utf-8"))
    await writer.drain()

    search_success = False
    try:
        # Listen for the search results on canal.memoria.respuesta
        for _ in range(3):
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not line:
                break

            event = json.loads(line.decode("utf-8").strip())
            topic = event.get("topic")
            data = event.get("data", {})
            logger.info(f"Test client read event on '{topic}': {data}")

            if (
                topic == "canal.memoria.respuesta"
                and data.get("request_id") == search_request_id
                and data.get("status") == "success"
            ):
                results = data.get("results", [])
                logger.info(f"Received search results from database: {results}")
                if len(results) > 0 and results[0].get("escala_magnitud") == "KB":
                    logger.info(
                        "VERIFICATION PASS: Semantic search returned indexed data with correct spatial metadata."
                    )
                    search_success = True
                    break
    except asyncio.TimeoutError:
        logger.error("Timeout waiting for search response event.")

    writer.close()
    await writer.wait_closed()

    if guardar_captured and search_success:
        logger.info("\n==============================================")
        logger.info("ALL PHASE 3 INTEGRATION TESTS PASSED SUCCESSFULLY!")
        logger.info("==============================================")
    else:
        logger.error("\n==============================================")
        logger.error(f"VERIFICATION FAILED: Guardar={guardar_captured}, Search={search_success}")
        logger.error("==============================================")


if __name__ == "__main__":
    asyncio.run(test_memory_pipeline())
