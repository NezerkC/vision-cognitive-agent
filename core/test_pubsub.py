import asyncio
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] TestClient: %(message)s")
logger = logging.getLogger("TestPubSub")


async def subscriber_client():
    logger.info("Subscriber connecting to event broker...")
    reader, writer = await asyncio.open_connection("127.0.0.1", 5000)

    # Subscribe to 'heartbeat'
    subscribe_msg = json.dumps({"action": "subscribe", "topics": ["heartbeat"]}) + "\n"
    writer.write(subscribe_msg.encode("utf-8"))
    await writer.drain()
    logger.info("Subscribed to 'heartbeat'")

    try:
        # Wait for one message
        line = await reader.readline()
        if line:
            message = json.loads(line.decode("utf-8").strip())
            logger.info(f"Received event: {message}")
            if message.get("topic") == "heartbeat" and message.get("data", {}).get("status") == "alive":
                logger.info("VERIFICATION SUCCESS: Message received matches expected payload.")
            else:
                logger.error("VERIFICATION FAILED: Unexpected message content.")
        else:
            logger.error("VERIFICATION FAILED: Connection closed without receiving messages.")
    except Exception as e:
        logger.error(f"Error in subscriber: {e}")
    finally:
        writer.close()
        await writer.wait_closed()


async def publisher_client():
    await asyncio.sleep(1)  # Let subscriber set up first
    logger.info("Publisher connecting to event broker...")
    reader, writer = await asyncio.open_connection("127.0.0.1", 5000)

    # Publish to 'heartbeat'
    publish_msg = (
        json.dumps({"action": "publish", "topic": "heartbeat", "data": {"status": "alive", "origin": "test_publisher"}})
        + "\n"
    )
    writer.write(publish_msg.encode("utf-8"))
    await writer.drain()
    logger.info("Published message to 'heartbeat'")

    writer.close()
    await writer.wait_closed()


async def main():
    try:
        await asyncio.gather(subscriber_client(), publisher_client())
    except Exception as e:
        logger.error(f"Failed to run test clients: {e}")


if __name__ == "__main__":
    asyncio.run(main())
