"""Configuration for Vision Cognitive Agent."""

import os
from pathlib import Path
from dataclasses import dataclass

@dataclass
class AgentConfig:
    db_path: Path = Path(os.getenv("VISION_DB_PATH", "./data/lancedb"))
    table_name: str = os.getenv("VISION_TABLE_NAME", "visual_memories")
    clip_model_name: str = os.getenv("CLIP_MODEL_NAME", "openai/clip-vit-base-patch32")
    llm_model: str = os.getenv("VISION_LLM_MODEL", "gemini/gemini-1.5-flash")
    embedding_dim: int = 512
    top_k_recall: int = 3
