"""Vector memory engine using LanceDB."""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

class VisualMemoryStore:
    """Manages visual memory storage and nearest-neighbor retrieval using LanceDB."""

    def __init__(self, db_path: Path, table_name: str = "visual_memories"):
        self.db_path = Path(db_path)
        self.table_name = table_name
        self._db = None
        self._table = None
        self._fallback_memories: List[Dict[str, Any]] = []

    def connect(self):
        """Connect to local LanceDB database."""
        try:
            import lancedb
            self.db_path.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(self.db_path))
            if self.table_name in self._db.table_names():
                self._table = self._db.open_table(self.table_name)
        except Exception as e:
            logger.warning(f"LanceDB local initialization fallback ({e}). Using in-memory store.")
            self._db = None

    def store_memory(self, memory_id: str, vector: List[float], label: str, metadata: Optional[Dict[str, Any]] = None):
        """Store a visual memory with its vector embedding and descriptive metadata."""
        record = {
            "id": memory_id,
            "vector": vector,
            "label": label,
            "metadata": str(metadata or {})
        }

        if self._db is not None:
            try:
                import pandas as pd
                df = pd.DataFrame([record])
                if self._table is None:
                    self._table = self._db.create_table(self.table_name, data=df)
                else:
                    self._table.add(df)
                return
            except Exception as e:
                logger.error(f"Failed to persist to LanceDB: {e}")

        # In-memory fallback
        self._fallback_memories.append(record)

    def search_similar(self, query_vector: List[float], limit: int = 3) -> List[Dict[str, Any]]:
        """Retrieve the top-K most similar visual memories for a query vector."""
        if self._table is not None:
            try:
                results = self._table.search(query_vector).limit(limit).to_list()
                return results
            except Exception as e:
                logger.error(f"LanceDB search failed ({e}), falling back to in-memory cosine.")

        # In-memory cosine search fallback
        if not self._fallback_memories:
            return []

        q_vec = np.array(query_vector)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        scored = []
        for mem in self._fallback_memories:
            m_vec = np.array(mem["vector"])
            m_norm = np.linalg.norm(m_vec)
            sim = float(np.dot(q_vec, m_vec) / (q_norm * m_norm)) if m_norm > 0 else 0.0
            scored.append((sim, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"id": m["id"], "label": m["label"], "_score": score, "metadata": m["metadata"]} for score, m in scored[:limit]]
