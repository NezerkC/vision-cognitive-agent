"""Cognitive agent orchestrating perception, memory, and LLM reasoning."""

import logging
from typing import Dict, Any, List, Optional
from vision_agent.config import AgentConfig
from vision_agent.perception import VisionPerceiver
from vision_agent.memory import VisualMemoryStore

logger = logging.getLogger(__name__)

class VisionCognitiveAgent:
    """Multimodal autonomous agent with episodic visual memory and reasoning capabilities."""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.perceiver = VisionPerceiver(model_name=self.config.clip_model_name)
        self.memory = VisualMemoryStore(db_path=self.config.db_path, table_name=self.config.table_name)
        self.memory.connect()

    def remember_image(self, image_path: str, label: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Process an image, extract its CLIP embedding, and store it in LanceDB."""
        embedding = self.perceiver.embed_image(image_path)
        memory_id = f"mem_{hash(image_path + label) & 0xFFFFFFFF:08x}"
        self.memory.store_memory(
            memory_id=memory_id,
            vector=embedding,
            label=label,
            metadata=metadata or {"source": image_path}
        )
        logger.info(f"Stored visual memory [{memory_id}] for: '{label}'")
        return memory_id

    def recall(self, query: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Recall relevant visual memories based on a semantic text query."""
        top_k = limit or self.config.top_k_recall
        query_vector = self.perceiver.embed_text(query)
        return self.memory.search_similar(query_vector, limit=top_k)

    def answer_query(self, user_question: str) -> str:
        """Reason over recalled visual memories and answer user question using LiteLLM."""
        recalled = self.recall(user_question)

        context_items = []
        for i, item in enumerate(recalled, 1):
            score = item.get("_score", item.get("_distance", "N/A"))
            context_items.append(f"{i}. Label: {item.get('label')} (relevance: {score})")

        context_str = "\n".join(context_items) if context_items else "No visual memories found."

        system_prompt = (
            "You are a Vision Cognitive Agent. You have access to recalled visual memories "
            "from an episodic LanceDB multimodal store. Answer the user question concisely "
            "based on the visual evidence provided."
        )

        user_content = f"Visual Context:\n{context_str}\n\nUser Question: {user_question}"

        try:
            import litellm
            response = litellm.completion(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=256
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"LiteLLM call skipped ({e}). Returning structured context summary.")
            return f"[Agent Reasoning]\nBased on episodic visual recall:\n{context_str}"
