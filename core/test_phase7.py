import asyncio
import json
import logging
import sys
import time

import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] TestPhase7: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TestPhase7")

async def test_gui_integration():
    api_url = "http://127.0.0.1:8000/upload_sensorial"
    ws_url = "ws://127.0.0.1:8000/ws"
    broker_host = "127.0.0.1"
    broker_port = 5000

    # 1. Start the event broker connection to spy on the broker directly
    logger.info("Connecting directly to event broker socket...")
    try:
        broker_reader, broker_writer = await asyncio.open_connection(broker_host, broker_port)
    except Exception as e:
        logger.error(f"Could not connect to event broker: {e}. Make sure core/main.py is running.")
        sys.exit(1)

    # Subscribe to target topics to verify event relays
    subscribe_msg = json.dumps({
        "action": "subscribe",
        "topics": ["canal.sensorial.archivo_recibido", "system"]
    }) + "\n"
    broker_writer.write(subscribe_msg.encode("utf-8"))
    await broker_writer.drain()
    logger.info("Subscribed to broker spy channels.")
    await asyncio.sleep(1.0)

    # 2. Upload file to FastAPI upload endpoint
    file_content = b"Contenido de prueba para inyeccion sensorial de archivos"
    filename = "test_upload.txt"
    logger.info(f"Simulating Drag & Drop upload of file '{filename}' to FastAPI...")

    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("file", file_content, filename=filename, content_type="text/plain")
            async with session.post(api_url, data=data, timeout=5.0) as resp:
                if resp.status == 200:
                    res_json = await resp.json()
                    logger.info(f"FastAPI upload replied status: {res_json.get('status')}. Path: {res_json.get('file_path')}")
                else:
                    logger.error(f"FastAPI upload endpoint failed with status {resp.status}")
    except Exception as e:
        logger.error(f"Failed to post file: {e}")

    # 3. Test WebSockets relay by connecting a mock client
    logger.info("Connecting mock visual client to FastAPI WebSocket...")
    try:
        async with aiohttp.ClientSession() as session, session.ws_connect(ws_url) as ws:
            logger.info("WebSocket connected successfully. Sending mock PANIC stop request...")
            # Send panic stopping trigger
            panic_payload = {
                "action": "panic"
            }
            await ws.send_str(json.dumps(panic_payload))
            logger.info("Panic trigger sent via WebSocket.")
            await asyncio.sleep(1.0)
    except Exception as e:
        logger.error(f"WebSocket client test failed: {e}")

    # 4. Spy listen loop to verify broker received the forwarded events
    file_event_verified = False
    panic_event_verified = False

    start_time = time.time()
    while time.time() - start_time < 15: # 15s timeout
        try:
            line = await asyncio.wait_for(broker_reader.readline(), timeout=1.0)
            if not line:
                break

            event = json.loads(line.decode("utf-8").strip())
            topic = event.get("topic")
            data = event.get("data", {})

            logger.info(f"Broker spy read event on '{topic}'")

            if topic == "canal.sensorial.archivo_recibido":
                if data.get("nombre") == filename:
                    logger.info("VERIFICATION PASS: Event broker received relayed file ingestion event!")
                    file_event_verified = True

            elif topic == "system":
                action = data.get("action")
                if action == "purge":
                    logger.info("VERIFICATION PASS: Event broker received relayed PANIC STOP purge command!")
                    panic_event_verified = True

            if file_event_verified and panic_event_verified:
                logger.info("\n" + "="*46 + "\nALL PHASE 7 INTEGRATION TESTS PASSED SUCCESSFULLY!\n" + "="*46 + "\n")
                sys.exit(0)

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Error reading broker: {e}")
            break

    logger.error(f"Test timed out. Progress: file_relayed={file_event_verified}, panic_relayed={panic_event_verified}")
    sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_gui_integration())
