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
    format="%(asctime)s [%(levelname)s] TestPhase6: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("TestPhase6")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMOTIONS_PATH = os.path.join(PROJECT_ROOT, "config", "emotions.json")


async def update_emotion(state: str):
    payload = {"estado": state, "intensidad": 0.9}
    with open(EMOTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    logger.info(f"Updated emotions.json to state: '{state}'")


async def test_integration():
    host = "127.0.0.1"
    port = 5000
    fastapi_url = "http://127.0.0.1:8000/webhook/externo"

    logger.info("Connecting to event broker...")
    try:
        reader, writer = await asyncio.open_connection(host, port)
    except Exception as e:
        logger.error(f"Could not connect to event broker: {e}. Make sure core/main.py is running.")
        sys.exit(1)

    # Subscribe to test topics
    subscribe_msg = (
        json.dumps(
            {
                "action": "subscribe",
                "topics": ["canal.cognitivo.respuesta", "canal.sensorial.periferico", "canal.imaginacion.respuesta"],
            }
        )
        + "\n"
    )
    writer.write(subscribe_msg.encode("utf-8"))
    await writer.drain()
    logger.info("Subscribed to Phase 6 topics.")
    await asyncio.sleep(1.0)

    # --- TEST 1: Emotion override temperature verification ---
    # Set emotion to "lógico"
    await update_emotion("lógico")
    req_logic_id = f"test-logic-{int(time.time())}"
    logger.info("Publishing peticion to LLM Router with state 'lógico'...")
    peticion_payload = {
        "action": "publish",
        "topic": "canal.cognitivo.peticion",
        "data": {
            "request_id": req_logic_id,
            "prompt": "Cuánto es 2+2?",
            "esfuerzo_requerido": "esfuerzo_bajo",
            "mock": True,
        },
    }
    writer.write((json.dumps(peticion_payload) + "\n").encode("utf-8"))
    await writer.drain()

    # --- TEST 2: ComfyUI integration verification ---
    req_image_id = f"test-image-{int(time.time())}"
    logger.info("Publishing petition to ComfyUI client...")
    imaginacion_payload = {
        "action": "publish",
        "topic": "canal.imaginacion.peticion",
        "data": {"request_id": req_image_id, "prompt": "Un cerebro holográfico brillante"},
    }
    writer.write((json.dumps(imaginacion_payload) + "\n").encode("utf-8"))
    await writer.drain()

    # --- TEST 3: FastAPI Webhook Relaying ---
    logger.info("Sending simulated external POST request to FastAPI Webhook...")
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"event": "git_push", "repo": "vision-os", "author": "NezerkC"}
            async with session.post(fastapi_url, json=payload, timeout=3.0) as resp:
                if resp.status == 200:
                    logger.info("FastAPI webhook endpoint returned HTTP 200.")
                else:
                    logger.error(f"FastAPI webhook endpoint failed with status {resp.status}")
    except Exception as e:
        logger.error(f"Failed to post to FastAPI server: {e}")

    # Listen loop to collect broker outputs
    logic_temp_correct = False
    image_received = False
    periferico_received = False

    start_time = time.time()
    while time.time() - start_time < 20:  # 20s timeout
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=1.0)
            if not line:
                break

            event = json.loads(line.decode("utf-8").strip())
            topic = event.get("topic")
            data = event.get("data", {})

            logger.info(f"Test client read event on '{topic}'")

            if topic == "canal.cognitivo.respuesta":
                if data.get("request_id") == req_logic_id:
                    response_str = data.get("response", "")
                    logger.info(f"VERIFICATION PASS: Received LLM reply: '{response_str}'")
                    # In mock mode, the router replies: "Mock response for prompt: ... using ... (temperature=0.0)"
                    if "temperature=0.0" in response_str:
                        logic_temp_correct = True
                        logger.info("VERIFICATION PASS: Emotion 'lógico' successfully forced temperature to 0.0!")

            elif topic == "canal.imaginacion.respuesta":
                if data.get("request_id") == req_image_id:
                    img_path = data.get("image_path")
                    logger.info(f"VERIFICATION PASS: Occipital imagination generated image path: '{img_path}'")
                    image_received = True

            elif topic == "canal.sensorial.periferico":
                logger.info(f"VERIFICATION PASS: Received relayed webhook data from broker: {data}")
                if data.get("event") == "git_push":
                    periferico_received = True

            if logic_temp_correct and image_received and periferico_received:
                logger.info(
                    "\n" + "=" * 46 + "\nALL PHASE 6 INTEGRATION TESTS PASSED SUCCESSFULLY!\n" + "=" * 46 + "\n"
                )
                # Reset emotions back to neutral before exiting
                await update_emotion("neutral")
                sys.exit(0)

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Error during listening: {e}")
            break

    # Reset emotions
    await update_emotion("neutral")
    logger.error(
        f"Test timed out. Progress: logic_temp={logic_temp_correct}, image={image_received}, webhook={periferico_received}"
    )
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_integration())
