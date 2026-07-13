import asyncio
import json
import logging
import os
import sys
import yaml
import lancedb
import pyarrow as pa
from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoTokenizer, AutoModel
import torch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] LobeTemporal: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("LanceDBManager")

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "memory_tiering.yaml"
)

class BGEM3Embedder:
    def __init__(self, model_name="BAAI/bge-m3", force_mock=False):
        self.force_mock = force_mock
        self.model = None
        self.tokenizer = None
        if not force_mock:
            try:
                logger.info(f"Loading local BGE-M3 embedding model: {model_name}...")
                # We disable model download warnings and load tokenizer and model
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModel.from_pretrained(model_name)
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                self.model.to(self.device)
                logger.info(f"BGE-M3 loaded on device: {self.device}")
            except Exception as e:
                logger.warning(f"Could not load BGE-M3 model locally: {e}. Falling back to deterministic mock embedding.")
                self.force_mock = True

    def embed_query(self, text: str) -> list[float]:
        if self.force_mock or not self.model:
            # Deterministic 1024-dim mock vector based on hashlib sha256
            import hashlib
            h = hashlib.sha256(text.encode("utf-8")).digest()
            vector = []
            for i in range(1024):
                # Generates a deterministic float value
                val = ((h[i % len(h)] + i) % 256) / 255.0 * 2.0 - 1.0
                vector.append(val)
            return vector
        
        try:
            inputs = self.tokenizer(text, padding=True, truncation=True, max_length=8192, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.model(**inputs)
            # BGE-M3: extract normalized CLS token embedding
            cls_embeddings = outputs.last_hidden_state[:, 0, :]
            normalized_embeddings = torch.nn.functional.normalize(cls_embeddings, p=2, dim=1)
            return normalized_embeddings[0].tolist()
        except Exception as e:
            logger.error(f"Error computing BGE-M3 embedding: {e}. Falling back to mock vector.")
            # Fallback to mock on runtime error
            import hashlib
            h = hashlib.sha256(text.encode("utf-8")).digest()
            return [float(((h[i % len(h)] + i) % 256) / 255.0 * 2.0 - 1.0) for i in range(1024)]


class LanceDBManager:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        self.host = host
        self.port = port
        self.db_path = "memoria_activa"
        self.load_config()
        self.db = None
        self.table = None
        self.embedder = None
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)

    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            storage_cfg = config.get("storage", {})
            self.db_path = storage_cfg.get("ssd_hot", {}).get("path", "memoria_activa")
            logger.info(f"Loaded database path from config: {self.db_path}")
        except Exception as e:
            logger.warning(f"Could not load memory_tiering.yaml: {e}. Defaulting to 'memoria_activa'.")
            self.db_path = "memoria_activa"

    def init_db(self, mock_embedder=False):
        try:
            os.makedirs(self.db_path, exist_ok=True)
            self.db = lancedb.connect(self.db_path)
            
            # Setup BGE-M3 Embedding Client
            self.embedder = BGEM3Embedder(force_mock=mock_embedder)

            # PyArrow schema for our 3D spatial index matrix (Base-3)
            schema = pa.schema([
                ("vector", pa.list_(pa.float32(), 1024)),  # BGE-M3 outputs 1024 dimensions
                ("text", pa.string()),
                ("coordenada_x", pa.float32()),
                ("coordenada_y", pa.float32()),
                ("temperatura_z", pa.float32()),
                ("escala_magnitud", pa.string()),
                ("metadata", pa.string())
            ])

            if "memoria_fractal" in self.db.table_names():
                self.table = self.db.open_table("memoria_fractal")
                logger.info("Opened existing table 'memoria_fractal'.")
            else:
                self.table = self.db.create_table("memoria_fractal", schema=schema)
                logger.info("Created new table 'memoria_fractal'.")

        except Exception as e:
            logger.critical(f"Failed to initialize database: {e}")
            raise e

    async def run(self):
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                # Subscribe to memory commands and system commands
                subscribe_msg = json.dumps({
                    "action": "subscribe",
                    "topics": ["canal.memoria", "system"]
                }) + "\n"
                writer.write(subscribe_msg.encode("utf-8"))
                await writer.drain()

                while True:
                    line = await reader.readline()
                    if not line:
                        break
                    
                    try:
                        event = json.loads(line.decode("utf-8").strip())
                    except json.JSONDecodeError:
                        continue

                    topic = event.get("topic")
                    data = event.get("data", {})

                    if topic == "system" and data.get("action") == "purge":
                        logger.warning("System purge signal received. Resetting search states.")
                        continue

                    if topic == "canal.memoria":
                        action = data.get("action")
                        if action == "guardar":
                            asyncio.create_task(self.handle_guardar(writer, data))
                        elif action == "buscar":
                            asyncio.create_task(self.handle_buscar(writer, data))
                        else:
                            logger.warning(f"Unknown action received on canal.memoria: {action}")

            except Exception as e:
                logger.error(f"Error in LanceDB loop: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def handle_guardar(self, writer, data: dict):
        try:
            text = data.get("text", "")
            meta = data.get("metadata", {})
            
            # Extract 3D base-3 matrix spatial metadata
            coord_x = float(data.get("coordenada_x", 0.0))
            coord_y = float(data.get("coordenada_y", 0.0))
            temp_z = float(data.get("temperatura_z", 100.0))  # Default > 50 (Hot / SSD)
            escala = str(data.get("escala_magnitud", "KB"))

            if not text:
                logger.warning("Attempted to save empty text. Skipped.")
                return

            # Chunk document using LangChain RecursiveCharacterTextSplitter
            chunks = self.text_splitter.split_text(text)
            logger.info(f"Splitting text into {len(chunks)} chunks for database insertion.")

            rows = []
            for chunk in chunks:
                # Compute embedding on threadpool to avoid blocking event loop
                loop = asyncio.get_running_loop()
                vector = await loop.run_in_executor(None, self.embedder.embed_query, chunk)
                
                rows.append({
                    "vector": vector,
                    "text": chunk,
                    "coordenada_x": coord_x,
                    "coordenada_y": coord_y,
                    "temperatura_z": temp_z,
                    "escala_magnitud": escala,
                    "metadata": json.dumps(meta)
                })

            # Save rows to LanceDB
            self.table.add(rows)
            logger.info(f"Successfully saved {len(chunks)} chunks to table.")

        except Exception as e:
            logger.error(f"Database error during guardar operation: {e}")
            await self.publish_error(writer, f"Guardar failed: {str(e)}")

    async def handle_buscar(self, writer, data: dict):
        request_id = data.get("request_id")
        query = data.get("query", "")
        top_n = int(data.get("top_n", 5))

        if not request_id or not query:
            logger.error("Malformed buscar request.")
            return

        try:
            # Compute query vector
            loop = asyncio.get_running_loop()
            vector = await loop.run_in_executor(None, self.embedder.embed_query, query)

            # Query LanceDB table
            results = self.table.search(vector).limit(top_n).to_list()
            
            # Format results
            clean_results = []
            for r in results:
                try:
                    meta = json.loads(r.get("metadata", "{}"))
                except Exception:
                    meta = {}
                clean_results.append({
                    "text": r.get("text"),
                    "coordenada_x": float(r.get("coordenada_x", 0.0)),
                    "coordenada_y": float(r.get("coordenada_y", 0.0)),
                    "temperatura_z": float(r.get("temperatura_z", 0.0)),
                    "escala_magnitud": r.get("escala_magnitud"),
                    "metadata": meta,
                    "score": float(r.get("_distance", 1.0))
                })

            response = {
                "action": "publish",
                "topic": "canal.memoria.respuesta",
                "data": {
                    "request_id": request_id,
                    "results": clean_results,
                    "status": "success"
                }
            }
            writer.write((json.dumps(response) + "\n").encode("utf-8"))
            await writer.drain()
            logger.info(f"Semantic search completed for query '{query}'. Published results.")

        except Exception as e:
            logger.error(f"Database error during buscar operation: {e}")
            await self.publish_error(writer, f"Buscar failed: {str(e)}")
            response = {
                "action": "publish",
                "topic": "canal.memoria.respuesta",
                "data": {
                    "request_id": request_id,
                    "error": str(e),
                    "status": "failed"
                }
            }
            try:
                writer.write((json.dumps(response) + "\n").encode("utf-8"))
                await writer.drain()
            except Exception:
                pass

    async def publish_error(self, writer, error_msg: str):
        try:
            error_event = {
                "action": "publish",
                "topic": "canal.memoria.error",
                "data": {
                    "error": error_msg
                }
            }
            writer.write((json.dumps(error_event) + "\n").encode("utf-8"))
            await writer.drain()
        except Exception as e:
            logger.error(f"Failed to publish error to broker: {e}")

if __name__ == "__main__":
    # Check if we want to force mock embedder via argument
    mock_emb = "--mock" in sys.argv
    manager = LanceDBManager()
    try:
        manager.init_db(mock_embedder=mock_emb)
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        logger.info("LanceDB Manager stopped.")
