import asyncio
import json
import logging
import os
import re
import sys

import lancedb
import pyarrow as pa
import torch
import yaml
from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoModel, AutoTokenizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] LobeTemporal: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("LanceDBManager")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "memory_tiering.yaml")


def sql_string_literal(value: str) -> str:
    """Quote a value as a SQL string literal for LanceDB filters (they accept no bound parameters)."""
    return "'" + value.replace("'", "''") + "'"


def emotion_where_clause(emotion_filter: str | None) -> str | None:
    """Build the metadata LIKE filter for an emotion, or None when there is nothing safe to filter by."""
    if not emotion_filter or emotion_filter == "neutral":
        return None
    if not re.fullmatch(r"[\w-]+", emotion_filter):
        logger.warning(f"Ignoring invalid emotion filter: {emotion_filter!r}")
        return None
    return f"metadata LIKE '%{emotion_filter}%'"


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
                logger.warning(
                    f"Could not load BGE-M3 model locally: {e}. Falling back to deterministic mock embedding."
                )
                self.force_mock = True

    def embed_query(self, text: str) -> list[float]:
        if self.force_mock or not self.model:
            import hashlib
            import re

            words = re.findall(r"\w+", text.lower())
            vector = [0.0] * 1024
            if not words:
                return vector
            for word in words:
                h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
                idx = h % 1024
                vector[idx] += 1.0
            norm = sum(x * x for x in vector) ** 0.5
            if norm > 0:
                vector = [x / norm for x in vector]
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
        self.cold_db_path = "memoria_historica"
        self.load_config()
        self.db = None
        self.cold_db = None
        self.table = None
        self.cold_table = None
        self.embedder = None
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)

    def load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            storage_cfg = config.get("storage", {})
            self.db_path = storage_cfg.get("ssd_hot", {}).get("path", "memoria_activa")
            self.cold_db_path = storage_cfg.get("hdd_cold", {}).get("path", "memoria_historica")
            logger.info(f"Loaded storage paths: Hot='{self.db_path}', Cold='{self.cold_db_path}'")
        except Exception as e:
            logger.warning(f"Could not load memory_tiering.yaml: {e}. Defaulting paths.")
            self.db_path = "memoria_activa"
            self.cold_db_path = "memoria_historica"

    def init_db(self, mock_embedder=False):
        try:
            os.makedirs(self.db_path, exist_ok=True)
            os.makedirs(self.cold_db_path, exist_ok=True)

            self.db = lancedb.connect(self.db_path)
            self.cold_db = lancedb.connect(self.cold_db_path)

            # Setup BGE-M3 Embedding Client
            self.embedder = BGEM3Embedder(force_mock=mock_embedder)

            # PyArrow schema for our 4D spatial index matrix (Euclidean + Cosine)
            schema = pa.schema(
                [
                    ("vector", pa.list_(pa.float32(), 1024)),  # BGE-M3 outputs 1024 dimensions
                    ("text", pa.string()),
                    ("coordenada_x", pa.float32()),
                    ("coordenada_y", pa.float32()),
                    ("coordenada_z", pa.float32()),
                    ("coordenada_w", pa.float32()),  # Metadata emotion/gravity dimension
                    ("escala_magnitud", pa.string()),
                    ("metadata", pa.string()),
                ]
            )

            # Hot Tier Table (HNSW index)
            if "memoria_fractal" in self.db.table_names():
                self.table = self.db.open_table("memoria_fractal")
                logger.info("Opened existing Hot table 'memoria_fractal'.")
            else:
                self.table = self.db.create_table("memoria_fractal", schema=schema)
                logger.info("Created new Hot table 'memoria_fractal'.")
                try:
                    self.table.create_fts_index("text")
                    logger.info("Created FTS index on Hot table for hybrid search.")
                except Exception as e:
                    logger.warning(f"Could not create FTS index on Hot table: {e}")

            # Cold Tier Table (PQ index)
            if "memoria_fractal" in self.cold_db.table_names():
                self.cold_table = self.cold_db.open_table("memoria_fractal")
                logger.info("Opened existing Cold table 'memoria_fractal'.")
            else:
                self.cold_table = self.cold_db.create_table("memoria_fractal", schema=schema)
                logger.info("Created new Cold table 'memoria_fractal'.")
                try:
                    self.cold_table.create_fts_index("text")
                    logger.info("Created FTS index on Cold table.")
                except Exception as e:
                    logger.warning(f"Could not create FTS index on Cold table: {e}")

        except Exception as e:
            logger.critical(f"Failed to initialize database: {e}")
            raise e

    def build_hot_cold_indices(self):
        """Builds HNSW index for Hot tier and PQ index for Cold tier."""
        try:
            if self.table and self.table.count_rows() >= 256:
                try:
                    self.table.create_index(metric="cosine", num_partitions=16, num_sub_vectors=64, index_type="IVF_PQ")
                    logger.info("Created HNSW/IVF index on Hot table.")
                except Exception as e:
                    logger.debug(f"Hot table index creation notice: {e}")

            if self.cold_table and self.cold_table.count_rows() >= 256:
                try:
                    self.cold_table.create_index(
                        metric="cosine", num_partitions=16, num_sub_vectors=32, index_type="IVF_PQ"
                    )
                    logger.info("Created PQ index on Cold table.")
                except Exception as e:
                    logger.debug(f"Cold table PQ index creation notice: {e}")
        except Exception as e:
            logger.warning(f"Index build deferred: {e}")

    async def run(self):
        while True:
            try:
                logger.info("Connecting to event broker...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info("Connected to event broker.")

                # Subscribe to memory commands and system commands
                subscribe_msg = json.dumps({"action": "subscribe", "topics": ["canal.memoria", "system"]}) + "\n"
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
                        elif action in ("buscar", "buscar_escrutinio"):
                            if action == "buscar_escrutinio":
                                data["escrutinio"] = True
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
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}

            # Extract 4D spatial metadata
            coord_x = float(data.get("coordenada_x", 0.0))
            coord_y = float(data.get("coordenada_y", 0.0))
            coord_z = float(data.get("coordenada_z", 0.0))
            coord_w = float(data.get("coordenada_w", 100.0))  # Emotional gravity / intrigue weight
            escala = str(data.get("escala_magnitud", "KB"))

            tier = meta.get("tier", "hot" if coord_w >= 70.0 else "cold")

            if not text:
                logger.warning("Attempted to save empty text. Skipped.")
                return

            # Chunk document using LangChain RecursiveCharacterTextSplitter
            chunks = self.text_splitter.split_text(text)
            logger.info(f"Splitting text into {len(chunks)} chunks for database insertion ({tier.upper()} tier).")

            rows = []
            loop = asyncio.get_running_loop()
            for chunk in chunks:
                vector = await loop.run_in_executor(None, self.embedder.embed_query, chunk)
                rows.append(
                    {
                        "vector": vector,
                        "text": chunk,
                        "coordenada_x": coord_x,
                        "coordenada_y": coord_y,
                        "coordenada_z": coord_z,
                        "coordenada_w": coord_w,
                        "escala_magnitud": escala,
                        "metadata": json.dumps(meta),
                    }
                )

            # Save rows to designated LanceDB tier table
            target_table = self.table if tier == "hot" else (self.cold_table or self.table)
            target_table.add(rows)
            logger.info(f"Successfully saved {len(chunks)} chunks to {tier.upper()} table.")

        except Exception as e:
            logger.error(f"Database error during guardar operation: {e}")
            if writer:
                await self.publish_error(writer, f"Guardar failed: {str(e)}")

    async def buscar_hibrido_rrf_impl(
        self,
        query: str,
        top_n: int = 5,
        k_rrf: int = 60,
        emotion_filter: str | None = None,
        vector: list[float] | None = None,
    ) -> list[dict]:
        """
        Executes Reciprocal Rank Fusion (RRF k=60) Hybrid Search combining dense vector similarity
        and Tantivy Full-Text Search (FTS). Calculates 4D spatial distance D² = X² + Y² + Z² + W².
        """
        import math

        if not query or not query.strip():
            return []

        loop = asyncio.get_running_loop()
        if vector is None and self.embedder is not None:
            vector = await loop.run_in_executor(None, self.embedder.embed_query, query)
        emotion_clause = emotion_where_clause(emotion_filter)

        # 1. Retrieve Vector Dense Search candidates from Hot & Cold tables
        vec_candidates = []
        for tbl in [self.table, self.cold_table]:
            if tbl is None:
                continue
            try:
                q = tbl.search(vector).limit(top_n * 3)
                if emotion_clause:
                    q = q.where(emotion_clause)
                vec_candidates.extend(q.to_list())
            except Exception as e:
                logger.debug(f"Dense vector query notice: {e}")

        # 2. Retrieve Full-Text Search (FTS) candidates from Hot & Cold tables
        fts_candidates = []
        for tbl in [self.table, self.cold_table]:
            if tbl is None:
                continue
            try:
                q = tbl.search(query, query_type="fts").limit(top_n * 3)
                if emotion_clause:
                    q = q.where(emotion_clause)
                fts_candidates.extend(q.to_list())
            except Exception as e:
                logger.debug(f"FTS search notice (Tantivy might be missing): {e}")

        # 3. Apply Reciprocal Rank Fusion (RRF k=60)
        rrf_scores: dict[str, float] = {}
        item_map: dict[str, dict] = {}

        for rank, item in enumerate(vec_candidates):
            text = item.get("text", "")
            if not text:
                continue
            key = text
            item_map[key] = item
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (k_rrf + rank + 1))

        for rank, item in enumerate(fts_candidates):
            text = item.get("text", "")
            if not text:
                continue
            key = text
            item_map[key] = item
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (k_rrf + rank + 1))

        # Fallback to dense if RRF was empty
        if not rrf_scores and vec_candidates:
            for rank, item in enumerate(vec_candidates):
                key = item.get("text", "")
                item_map[key] = item
                rrf_scores[key] = 1.0 / (k_rrf + rank + 1)

        # 4. Re-rank results using 4D Spatial Distance: D² = X² + Y² + Z² + W²
        combined_results = []
        for key, rrf_score in rrf_scores.items():
            r = item_map[key]
            cx = float(r.get("coordenada_x", 0.0))
            cy = float(r.get("coordenada_y", 0.0))
            cz = float(r.get("coordenada_z", 0.0))
            cw = float(r.get("coordenada_w", 0.0))

            d2 = cx * cx + cy * cy + cz * cz + cw * cw
            dist_4d = math.sqrt(d2)

            w_bonus = (cw / 100.0) * 0.2
            final_score = rrf_score + w_bonus

            meta = r.get("metadata", "{}")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}

            combined_results.append(
                {
                    "text": r.get("text"),
                    "coordenada_x": cx,
                    "coordenada_y": cy,
                    "coordenada_z": cz,
                    "coordenada_w": cw,
                    "distancia_4d": round(dist_4d, 4),
                    "rrf_score": round(rrf_score, 6),
                    "final_score": round(final_score, 6),
                    "escala_magnitud": r.get("escala_magnitud", "KB"),
                    "metadata": meta,
                }
            )

        combined_results.sort(key=lambda item: item["final_score"], reverse=True)
        return combined_results[:top_n]

    async def buscar_con_escrutinio_progresivo(
        self,
        query: str,
        top_k_inicial: int = 3,
        umbral_similitud_inicial: float = 0.7,
        max_intentos: int = 10,
        paso_adaptativo: int = 3,
        incremento_top_k: int = 2,
        decremento_umbral: float = 0.05,
        emotion_filter: str | None = None,
    ) -> dict:
        """
        Algoritmo de escrutinio progresivo que relaja dinámicamente top_k y umbral_similitud
        cada `paso_adaptativo` intentos (máximo `max_intentos`) si no se obtienen resultados
        suficientes dentro del umbral. Retorna metadatos de telemetría y fallback seguro.
        """
        if not query or not query.strip():
            return {
                "status": "fallback",
                "results": [],
                "telemetria": {
                    "intentos": 0,
                    "top_k_final": top_k_inicial,
                    "umbral_final": umbral_similitud_inicial,
                    "exito": False,
                    "motivo": "Consulta vacía",
                },
            }

        loop = asyncio.get_running_loop()
        query_vector = None
        if self.embedder is not None:
            query_vector = await loop.run_in_executor(None, self.embedder.embed_query, query)

        current_top_k = top_k_inicial
        current_umbral = umbral_similitud_inicial
        intentos = 0

        for intento in range(1, max_intentos + 1):
            intentos = intento
            candidatos = await self.buscar_hibrido_rrf_impl(
                query=query, top_n=current_top_k, emotion_filter=emotion_filter, vector=query_vector
            )

            filtrados = [c for c in candidatos if c.get("final_score", 0.0) >= current_umbral]

            if filtrados:
                logger.info(
                    f"Escrutinio progresivo exitoso en intento {intento}/{max_intentos}. "
                    f"Resultados: {len(filtrados)}, top_k: {current_top_k}, umbral: {current_umbral:.4f}"
                )
                return {
                    "status": "success",
                    "results": filtrados,
                    "telemetria": {
                        "intentos": intento,
                        "top_k_final": current_top_k,
                        "umbral_final": round(current_umbral, 4),
                        "exito": True,
                    },
                }

            if intento % paso_adaptativo == 0:
                current_top_k += incremento_top_k
                current_umbral = max(0.0, current_umbral - decremento_umbral)
                logger.info(
                    f"Escrutinio progresivo: relajando parámetros tras intento {intento}. "
                    f"Nuevo top_k: {current_top_k}, nuevo umbral: {current_umbral:.4f}"
                )

        logger.warning(
            f"Escrutinio progresivo agotó los {max_intentos} intentos sin superar el umbral. Activando fallback seguro."
        )
        return {
            "status": "fallback",
            "results": [],
            "telemetria": {
                "intentos": intentos,
                "top_k_final": current_top_k,
                "umbral_final": round(current_umbral, 4),
                "exito": False,
                "motivo": "Sin coincidencias dentro del margen de confianza",
            },
        }

    async def handle_buscar(self, writer, data: dict):
        query = data.get("query", "")
        top_n = data.get("top_n", 3)
        request_id = data.get("request_id", "default")
        emotion_filter = data.get("emotion_filter", "neutral")
        usar_escrutinio = data.get("escrutinio", False) or data.get("modo") == "escrutinio"

        if not query:
            return

        try:
            if usar_escrutinio:
                top_k_ini = data.get("top_k_inicial", top_n)
                umbral_ini = float(data.get("umbral_similitud_inicial", 0.7))
                max_int = int(data.get("max_intentos", 10))
                paso_adap = int(data.get("paso_adaptativo", 3))

                res = await self.buscar_con_escrutinio_progresivo(
                    query=query,
                    top_k_inicial=top_k_ini,
                    umbral_similitud_inicial=umbral_ini,
                    max_intentos=max_int,
                    paso_adaptativo=paso_adap,
                    emotion_filter=emotion_filter,
                )
                clean_results = res.get("results", [])
                status = res.get("status", "success")
                telemetria = res.get("telemetria", {})
            else:
                clean_results = await self.buscar_hibrido_rrf_impl(
                    query=query, top_n=top_n, emotion_filter=emotion_filter
                )
                status = "success"
                telemetria = None

            response_data = {"request_id": request_id, "results": clean_results, "status": status}
            if telemetria:
                response_data["telemetria"] = telemetria

            response = {"action": "publish", "topic": "canal.memoria.respuesta", "data": response_data}
            if writer:
                writer.write((json.dumps(response) + "\n").encode("utf-8"))
                await writer.drain()
            logger.info(f"Search completed for '{query}'. Found {len(clean_results)} items (status={status}).")

        except Exception as e:
            logger.error(f"Database error during buscar operation: {e}")
            if writer:
                await self.publish_error(writer, f"Buscar failed: {str(e)}")
                response = {
                    "action": "publish",
                    "topic": "canal.memoria.respuesta",
                    "data": {"request_id": request_id, "error": str(e), "status": "failed"},
                }
                try:
                    writer.write((json.dumps(response) + "\n").encode("utf-8"))
                    await writer.drain()
                except Exception:
                    pass

    async def publish_error(self, writer, error_msg: str):
        if not writer:
            return
        try:
            error_event = {"action": "publish", "topic": "canal.memoria.error", "data": {"error": error_msg}}
            writer.write((json.dumps(error_event) + "\n").encode("utf-8"))
            await writer.drain()
        except Exception as e:
            logger.error(f"Failed to publish error to broker: {e}")


if __name__ == "__main__":
    mock_emb = "--mock" in sys.argv
    manager = LanceDBManager()
    try:
        manager.init_db(mock_embedder=mock_emb)
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        logger.info("LanceDB Manager stopped.")
