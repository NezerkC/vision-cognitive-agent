"""
cargador_datasets.py — Ingesta de datos al torrente sanguíneo de Visión OS.

Ofrece dos modos:
  1. guardar_recuerdo()  → guarda directamente en LanceDB (útil para scripts)
  2. Ingesta desde HuggingFace o archivos locales

Uso:
    python memoria/cargador_datasets.py
    python memoria/cargador_datasets.py --desde-archivo "./mi_dataset.jsonl"
"""

import asyncio
import json
import logging
import os
import sys

# ─────────────────────────────────────────────────────────────────
# Configurar logging
# ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Cargador: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("CargadorDatasets")

# Ruta al proyecto
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ─────────────────────────────────────────────────────────────────
# guardar_recuerdo — API directa a LanceDB
# ─────────────────────────────────────────────────────────────────
_guardar_manager = None


async def guardar_recuerdo(
    texto: str,
    metadata: dict | None = None,
    coordenada_x: float = 0.0,
    coordenada_y: float = 0.0,
    temperatura_z: float = 100.0,
    escala_magnitud: str = "KB",
) -> bool:
    """
    Guarda un recuerdo directamente en LanceDB (sin pasar por el broker).

    Args:
        texto: Contenido textual a guardar.
        metadata: Dict con metadatos adicionales (origen, edificio, etc.).
        coordenada_x, coordenada_y: Coordenadas en el cubo de memoria.
        temperatura_z: >50 → SSD (caliente), <50 → HDD (frío).
        escala_magnitud: "KB", "MB", etc.

    Returns:
        True si se guardó correctamente.
    """
    global _guardar_manager

    if _guardar_manager is None:
        from memoria.lancedb_manager import LanceDBManager

        _guardar_manager = LanceDBManager()
        _guardar_manager.init_db(mock_embedder=False)

    # The memory schema has no temperatura_z column: the "temperature" is the W weight, and it picks the tier.
    payload = {
        "text": texto,
        "coordenada_x": coordenada_x,
        "coordenada_y": coordenada_y,
        "coordenada_z": 0.0,
        "coordenada_w": temperatura_z,
        "escala_magnitud": escala_magnitud,
        "metadata": {**(metadata or {}), "tier": "hot" if temperatura_z > 50 else "cold"},
    }
    saved = await _guardar_manager.handle_guardar(None, payload)
    if saved:
        logger.info("✅ Recuerdo guardado en la memoria.")
    return saved


# ─────────────────────────────────────────────────────────────────
# Ingesta desde HuggingFace
# ─────────────────────────────────────────────────────────────────
async def ingerir_dataset_huggingface(
    dataset_name: str = "iamtarun/python_code_instructions_18k_alpaca",
    max_ejemplos: int = 100,
    edificio: str = "torre_programacion",
    coordenada_x: float = 10.0,
    coordenada_y: float = 5.0,
    temperatura_z: float = 20.0,  # Frío (HDD)
):
    """
    Carga ejemplos desde un dataset de HuggingFace y los guarda en LanceDB.
    """
    try:
        from langchain_community.document_loaders import HuggingFaceDatasetLoader
    except ImportError:
        logger.error("❌ Falta 'langchain-community'. Instalalo con:\n   pip install langchain-community datasets")
        return

    logger.info(f"📚 Descargando dataset '{dataset_name}' desde HuggingFace...")
    try:
        loader_hf = HuggingFaceDatasetLoader(dataset_name, page_content_column="instruction")
        docs = loader_hf.load()[:max_ejemplos]
    except Exception as e:
        logger.error(f"❌ Error cargando dataset: {e}")
        return

    logger.info(f"📦 {len(docs)} ejemplos obtenidos. Guardando en LanceDB...")

    for i, doc in enumerate(docs):
        texto = f"Instrucción: {doc.page_content}\nCódigo: {doc.metadata.get('output', '')}"
        metadata = {"origen": "dataset_hf", "dataset": dataset_name, "edificio": edificio, "indice": i}
        await guardar_recuerdo(
            texto=texto,
            metadata=metadata,
            coordenada_x=coordenada_x,
            coordenada_y=coordenada_y,
            temperatura_z=temperatura_z,
        )
        if (i + 1) % 10 == 0:
            logger.info(f"⏳ Progreso: {i + 1}/{len(docs)}")

    logger.info(f"✅ Ingesta completada: {len(docs)} ejemplos guardados en '{edificio}'.")


# ─────────────────────────────────────────────────────────────────
# Ingesta desde archivo local (JSONL)
# ─────────────────────────────────────────────────────────────────
async def ingerir_desde_archivo(
    ruta: str,
    campo_texto: str = "text",
    campo_salida: str = "output",
    max_ejemplos: int = 200,
    edificio: str = "torre_programacion",
):
    """
    Carga ejemplos desde un archivo JSONL local.

    Formato esperado por línea:
      {"instruction": "...", "output": "..."}
      o
      {"text": "...", ...}
    """
    if not os.path.exists(ruta):
        logger.error(f"❌ Archivo no encontrado: {ruta}")
        return

    logger.info(f"📂 Leyendo archivo local: {ruta}")
    ejemplos = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                try:
                    ejemplos.append(json.loads(linea))
                except json.JSONDecodeError:
                    continue
            if len(ejemplos) >= max_ejemplos:
                break

    logger.info(f"📦 {len(ejemplos)} ejemplos cargados. Guardando...")

    for i, item in enumerate(ejemplos):
        texto = f"Instrucción: {item.get(campo_texto, '')}\nCódigo: {item.get(campo_salida, '')}"
        metadata = {"origen": "archivo_local", "archivo": os.path.basename(ruta), "edificio": edificio, "indice": i}
        await guardar_recuerdo(texto=texto, metadata=metadata, coordenada_x=10.0, coordenada_y=5.0, temperatura_z=20.0)
        if (i + 1) % 25 == 0:
            logger.info(f"⏳ Progreso: {i + 1}/{len(ejemplos)}")

    logger.info(f"✅ Ingesta local completada: {len(ejemplos)} ejemplos.")


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    async def main():
        if "--desde-archivo" in sys.argv:
            idx = sys.argv.index("--desde-archivo")
            ruta = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
            if ruta:
                await ingerir_desde_archivo(ruta)
            else:
                logger.error("Usá: python cargador_datasets.py --desde-archivo ./ruta/al/archivo.jsonl")
        else:
            logger.info("🏗️ [CIMIENTOS] Iniciando ingesta de Dataset de Programación...")
            await ingerir_dataset_huggingface(max_ejemplos=50)

    asyncio.run(main())
