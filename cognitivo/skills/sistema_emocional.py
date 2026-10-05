import json
import logging
import os

from langchain_core.tools import tool

logger = logging.getLogger("SistemaEmocional")

EMOTIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "emotions.json"
)


@tool
def actualizar_emocion(estado: str, intensidad: float) -> str:
    """
    Actualiza el estado emocional actual del sistema de Visión OS.
    El estado puede ser: 'neutral', 'alegría', 'tristeza', 'enojo', 'intriga', 'lógico', 'creativo'.
    La intensidad debe ser un float entre 0.0 y 1.0.
    """
    try:
        # Validar intensidad
        intensidad = max(0.0, min(1.0, float(intensidad)))

        # Cargar datos
        emociones = {"estado": estado, "intensidad": intensidad}

        # Guardar en emotions.json
        os.makedirs(os.path.dirname(EMOTIONS_PATH), exist_ok=True)
        with open(EMOTIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(emociones, f)

        logger.info(f"Emotional state updated successfully to: {estado} (intensity={intensidad})")
        return f"Éxito: Estado emocional actualizado a '{estado}' con intensidad {intensidad}."
    except Exception as e:
        logger.error(f"Failed to update emotions: {e}")
        return f"Error al actualizar el estado emocional: {str(e)}"
