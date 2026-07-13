import asyncio
import logging
import sys

# Configure logging cleanly
logger = logging.getLogger("GestorModelosLocales")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] GestorModelosLocales: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


async def is_model_available_locally(model_tag: str) -> bool:
    """
    Checks if the given Ollama model is already downloaded locally by querying 'ollama list'.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "ollama", "list",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        if process.returncode == 0:
            output = stdout.decode("utf-8", errors="ignore")
            # Check if model name exists in the list output
            return model_tag in output
        return False
    except FileNotFoundError:
        logger.warning("Ollama command-line executable not found in PATH.")
        return False
    except Exception as e:
        logger.warning(f"Error checking local Ollama models: {e}")
        return False


async def pull_model_if_missing(model_name: str, mock: bool = False) -> bool:
    """
    Strips the 'ollama/' prefix and pulls the model from the Ollama registry if it is not already available.
    Returns: True if model is available/downloaded, False otherwise.
    """
    if not model_name.startswith("ollama/"):
        return True  # Non-Ollama models (APIs) are assumed available

    model_tag = model_name.replace("ollama/", "", 1)

    if mock:
        logger.info(f"[MOCK] Simulating pull for Ollama model '{model_tag}'...")
        await asyncio.sleep(1.0)
        return True

    # 1. Check if model is already downloaded
    logger.info(f"Checking if local model '{model_tag}' is available...")
    if await is_model_available_locally(model_tag):
        logger.info(f"Model '{model_tag}' is already available locally.")
        return True

    # 2. Pull the model dynamically
    logger.warning(f"Model '{model_tag}' is missing! Initiating dynamic 'ollama pull {model_tag}'...")
    try:
        process = await asyncio.create_subprocess_exec(
            "ollama", "pull", model_tag,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        # Read outputs line by line to show download progress in real-time logs
        async def log_stream(stream):
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="ignore").strip()
                if decoded:
                    logger.info(f"[Ollama Pull] {decoded}")

        await asyncio.gather(
            log_stream(process.stdout),
            log_stream(process.stderr),
            process.wait()
        )

        if process.returncode == 0:
            logger.info(f"Successfully downloaded and loaded local model '{model_tag}'.")
            return True
        else:
            logger.error(f"'ollama pull {model_tag}' failed with exit code {process.returncode}.")
            return False

    except FileNotFoundError:
        logger.critical("Failed to pull model: Ollama is not installed on this system.")
        return False
    except Exception as e:
        logger.critical(f"Unexpected error while pulling local model '{model_tag}': {e}")
        return False


if __name__ == "__main__":
    # Test script standalone execution
    if len(sys.argv) > 1:
        test_model = sys.argv[1]
        logger.info(f"Testing local model check/pull for '{test_model}'...")
        asyncio.run(pull_model_if_missing(test_model))
    else:
        logger.info("Usage: python gestor_modelos_locales.py <ollama/model_name>")
