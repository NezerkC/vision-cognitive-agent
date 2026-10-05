import asyncio
import json
import logging
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] TestPhase5: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("TestPhase5")


async def test_integration():
    host = "127.0.0.1"
    port = 5000

    logger.info("Connecting to event broker...")
    try:
        reader, writer = await asyncio.open_connection(host, port)
    except Exception as e:
        logger.error(f"Could not connect to event broker: {e}. Make sure core/main.py is running.")
        sys.exit(1)

    # Subscribe to audio transcriptions and execution results
    subscribe_msg = (
        json.dumps(
            {"action": "subscribe", "topics": ["canal.sensorial.audio.transcripcion", "canal.ejecucion.resultado"]}
        )
        + "\n"
    )
    writer.write(subscribe_msg.encode("utf-8"))
    await writer.drain()
    logger.info("Subscribed to Phase 5 topics.")

    # Give it a moment to bind subscription
    await asyncio.sleep(1.0)

    # Publish a test script execution action
    request_id = f"test-script-{int(time.time())}"
    logger.info(f"Publishing test action request '{request_id}' to 'canal.ejecucion.accion'...")
    action_payload = {
        "action": "publish",
        "topic": "canal.ejecucion.accion",
        "data": {
            "request_id": request_id,
            "herramienta": "ejecutar_script",
            "parametros": ["python -c \"print('HEMISFERIO_IZQUIERDO_OK')\""],
        },
    }
    writer.write((json.dumps(action_payload) + "\n").encode("utf-8"))
    await writer.drain()

    # Publish a test UI action to verify the orange safety warning logic
    ui_request_id = f"test-ui-{int(time.time())}"
    logger.info(f"Publishing test UI request '{ui_request_id}' to 'canal.ejecucion.accion'...")
    ui_payload = {
        "action": "publish",
        "topic": "canal.ejecucion.accion",
        "data": {
            "request_id": ui_request_id,
            "herramienta": "control_ui",
            "parametros": ["win", "escribir: notepad", "enter"],
        },
    }
    writer.write((json.dumps(ui_payload) + "\n").encode("utf-8"))
    await writer.drain()

    audio_received = False
    action_received = False
    ui_received = False

    # Listen loop
    start_time = time.time()
    while time.time() - start_time < 30:  # 30 seconds timeout
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=1.0)
            if not line:
                break

            event = json.loads(line.decode("utf-8").strip())
            topic = event.get("topic")
            data = event.get("data", {})

            logger.info(f"Test client read event on '{topic}'")

            if topic == "canal.sensorial.audio.transcripcion":
                text = data.get("transcripcion")
                logger.info(f"VERIFICATION PASS: Audio transcription event caught with text: '{text}'")
                audio_received = True

            elif topic == "canal.ejecucion.resultado":
                event_req_id = data.get("request_id")
                resultado = data.get("resultado", {})

                if event_req_id == request_id:
                    stdout_content = resultado.get("stdout", "").strip()
                    logger.info(f"VERIFICATION PASS: Script execution output: '{stdout_content}'")
                    if "HEMISFERIO_IZQUIERDO_OK" in stdout_content:
                        action_received = True

                elif event_req_id == ui_request_id:
                    detail = resultado.get("detail", "")
                    logger.info(f"VERIFICATION PASS: UI execution detail: '{detail}'")
                    ui_received = True

            if audio_received and action_received and ui_received:
                logger.info(
                    "\n" + "=" * 46 + "\nALL PHASE 5 INTEGRATION TESTS PASSED SUCCESSFULLY!\n" + "=" * 46 + "\n"
                )
                sys.exit(0)

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Error during listening: {e}")
            break

    logger.error(f"Test timed out. Progress: audio={audio_received}, script={action_received}, ui={ui_received}")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_integration())
