"""Recompute every stored vector with the current embedder.

Usage: python -m memoria.reindex [STORE_PATH ...]

Without arguments it re-indexes the hot and cold memory stores from config/memory_tiering.yaml and the notebook
store. Run it once when Vision refuses to start because a store holds vectors from another embedder, for example
the hash vectors older versions wrote silently when BGE-M3 failed to load. Rows keep their text and metadata.
"""

import os
import sys
from collections.abc import Callable

from memoria.lancedb_manager import BGEM3Embedder, LanceDBManager, reindex_store

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_store_paths() -> list[str]:
    from cognitivo.cuadernos_manager import LANCE_DB_PATH

    manager = LanceDBManager()
    return [os.path.join(PROJECT_ROOT, p) for p in (manager.db_path, manager.cold_db_path)] + [LANCE_DB_PATH]


def main(argv: list[str] | None = None, embedder_factory: Callable = BGEM3Embedder) -> int:
    paths = (sys.argv[1:] if argv is None else argv) or default_store_paths()
    embedder = embedder_factory()
    total = 0
    for path in paths:
        if not os.path.isdir(path):
            print(f"Skipping {path}: not found")
            continue
        count = reindex_store(path, embedder)
        total += count
        print(f"{path}: {count} rows re-embedded with {embedder.model_id}")
    print(f"Done: {total} rows re-embedded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
