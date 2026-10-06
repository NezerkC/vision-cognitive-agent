import asyncio
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] TestPhase4: %(message)s")
logger = logging.getLogger("TestPhase4")


async def test_sensory_pipeline():
    logger.info("Connecting to event broker...")
    reader, writer = await asyncio.open_connection("127.0.0.1", 5000)

    # Subscribe to vision captures and interpreted contexts
    subscribe_msg = (
        json.dumps({"action": "subscribe", "topics": ["canal.sensorial.vision", "canal.sistema.contexto_actual"]})
        + "\n"
    )
    writer.write(subscribe_msg.encode("utf-8"))
    await writer.drain()
    logger.info("Subscribed to vision and system context topics.")

    vision_captured = False
    context_captured = False

    try:
        # We listen for events. Since capture frequency is 5 seconds, we wait up to 10 seconds.
        logger.info("Waiting for Lóbulo Parietal screenshot and Hemisferio Derecho context events...")
        for _ in range(5):
            line = await asyncio.wait_for(reader.readline(), timeout=12.0)
            if not line:
                break

            event = json.loads(line.decode("utf-8").strip())
            topic = event.get("topic")
            data = event.get("data", {})
            logger.info(f"Test client read event on '{topic}'")

            if topic == "canal.sensorial.vision" and "image" in data:
                logger.info("VERIFICATION PASS: Screenshot captured and base64 string received.")
                vision_captured = True

            elif topic == "canal.sistema.contexto_actual" and "contexto" in data:
                logger.info(f"VERIFICATION PASS: Context successfully updated: {data.get('contexto')}")
                context_captured = True
                break

    except TimeoutError:
        logger.error("Timeout waiting for sensory pipeline events.")
    finally:
        writer.close()
        await writer.wait_closed()

    if vision_captured and context_captured:
        logger.info("\n==============================================")
        logger.info("ALL PHASE 4 INTEGRATION TESTS PASSED SUCCESSFULLY!")
        logger.info("==============================================")
    else:
        logger.error("\n==============================================")
        logger.error(f"VERIFICATION FAILED: Vision={vision_captured}, Context={context_captured}")
        logger.error("==============================================")


if __name__ == "__main__":
    asyncio.run(test_sensory_pipeline())
