"""Unit tests for Vision Cognitive Agent."""

import unittest
from unittest.mock import patch, MagicMock
from vision_agent.config import AgentConfig
from vision_agent.perception import VisionPerceiver
from vision_agent.memory import VisualMemoryStore
from vision_agent.agent import VisionCognitiveAgent

class TestVisionCognitiveAgent(unittest.TestCase):

    def setUp(self):
        self.config = AgentConfig(db_path="./test_data/lancedb", table_name="test_memories")
        self.agent = VisionCognitiveAgent(config=self.config)

    def test_mock_perception_text_embedding(self):
        perceiver = VisionPerceiver()
        vector = perceiver.embed_text("a red sports car")
        self.assertEqual(len(vector), 512)

    def test_mock_perception_image_embedding(self):
        perceiver = VisionPerceiver()
        # Mocking an image or string path with lazy mock
        vector = perceiver.embed_image("non_existent_dummy_path.jpg")
        self.assertEqual(len(vector), 512)

    def test_store_and_recall_memory(self):
        mem_id = self.agent.remember_image("sample.jpg", "A diagram of microservices architecture")
        self.assertTrue(mem_id.startswith("mem_"))

        recalled = self.agent.recall("microservices architecture", limit=1)
        self.assertGreaterEqual(len(recalled), 1)
        self.assertIn("microservices", recalled[0]["label"])

    def test_agent_answer_query_fallback(self):
        self.agent.remember_image("server.png", "A high availability database cluster")
        response = self.agent.answer_query("Where is the database cluster?")
        self.assertIsInstance(response, str)
        self.assertIn("database cluster", response)

if __name__ == "__main__":
    unittest.main()
