import asyncio
import json
import logging
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] TestIntriga: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TestIntriga")

async def test_ticketing():
    host = "127.0.0.1"
    port = 5000

    logger.info("Connecting to event broker...")
    try:
        reader, writer = await asyncio.open_connection(host, port)
    except Exception as e:
        logger.error(f"Could not connect to event broker: {e}. Make sure core/main.py is running.")
        sys.exit(1)

    # Subscribe to required topics to spy on the messaging pipeline
    subscribe_msg = json.dumps({
        "action": "subscribe",
        "topics": [
            "canal.sistema.anuncios",
            "canal.cognitivo.peticion",
            "canal.memoria"
        ]
    }) + "\n"
    writer.write(subscribe_msg.encode("utf-8"))
    await writer.drain()
    logger.info("Subscribed to test topics.")
    await asyncio.sleep(1.0)

    # 1. Publish simulated context showing an anomaly
    anomaly_text = "Driver Radeon crashed with code 43"
    logger.info("Publishing anomaly event to 'canal.sistema.contexto_actual'...")
    context_payload = {
        "action": "publish",
        "topic": "canal.sistema.contexto_actual",
        "data": {
            "contexto": f"ANOMALIA_DETECTADA: {anomaly_text}",
            "timestamp": time.time()
        }
    }
    writer.write((json.dumps(context_payload) + "\n").encode("utf-8"))
    await writer.drain()

    # Variables to track pipeline completion
    ticket_announced = False
    voice_confirmed = False
    formulation_requested = False
    solution_saved = False

    start_time = time.time()
    while time.time() - start_time < 20: # 20s timeout
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=1.0)
            if not line:
                break

            event = json.loads(line.decode("utf-8").strip())
            topic = event.get("topic")
            data = event.get("data", {})

            logger.info(f"Test client read event on '{topic}'")

            if topic == "canal.sistema.anuncios":
                msg = data.get("mensaje", "")
                if anomaly_text in msg:
                    logger.info("VERIFICATION PASS: Ticket proposal announced by Protocolo de Intriga!")
                    ticket_announced = True

                    # 2. Simulate user confirming via voice transcription
                    logger.info("Publishing confirmation voice transcription 'si, procede'...")
                    confirm_payload = {
                        "action": "publish",
                        "topic": "canal.sensorial.audio.transcripcion",
                        "data": {
                            "transcripcion": "si, procede a investigar por favor",
                            "timestamp": time.time()
                        }
                    }
                    writer.write((json.dumps(confirm_payload) + "\n").encode("utf-8"))
                    await writer.drain()
                    voice_confirmed = True

            elif topic == "canal.cognitivo.peticion":
                prompt = data.get("prompt", "")
                if anomaly_text in prompt:
                    logger.info("VERIFICATION PASS: Lóbulo Frontal received search query formulation request!")
                    formulation_requested = True

            elif topic == "canal.memoria":
                action = data.get("action")
                text = data.get("text", "")
                if action == "guardar" and anomaly_text in text:
                    logger.info("VERIFICATION PASS: Solution successfully saved to LanceDB!")
                    solution_saved = True

            if ticket_announced and voice_confirmed and formulation_requested and solution_saved:
                logger.info("\n" + "="*48 + "\nALL TICKETING INTEGRATION TESTS PASSED SUCCESSFULLY!\n" + "="*48 + "\n")
                sys.exit(0)

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Error in test loop: {e}")
            break

    logger.error(f"Test timed out. Progress: announced={ticket_announced}, confirmed={voice_confirmed}, formulated={formulation_requested}, saved={solution_saved}")
    sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_ticketing())
