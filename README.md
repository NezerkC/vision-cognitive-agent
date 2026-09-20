# 👁️ Vision Cognitive Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Vector DB: LanceDB](https://img.shields.io/badge/Vector_DB-LanceDB-1E1E1E.svg)](https://lancedb.com)
[![Vision: CLIP](https://img.shields.io/badge/Embeddings-OpenAI_CLIP-412991.svg)](https://github.com/openai/CLIP)
[![LLM: LiteLLM](https://img.shields.io/badge/LLM_Gateway-LiteLLM-5A67D8.svg)](https://litellm.ai)

**Vision Cognitive Agent** is an autonomous multimodal architecture that combines episodic visual memory (via **LanceDB** vector indexing), zero-shot multimodal embeddings (**CLIP**), and multi-provider reasoning (**LiteLLM**).

---

## 🏗️ Cognitive Architecture

```mermaid
graph TD
    User([User Query / Image]) --> CLI[CLI / Agent Interface]
    
    subgraph "Perception Layer"
        CLI --> CLIP[VisionPerceiver (CLIP ViT)]
        CLIP --> Vector[512d Multimodal Vector]
    end

    subgraph "Episodic Memory Layer"
        Vector --> LanceDB[(LanceDB Vector Store)]
        LanceDB --> RecalledMemories[Top-K Semantic Visual Recall]
    end

    subgraph "Cognitive Reasoning Layer"
        RecalledMemories --> PromptEngine[Context Assembler]
        PromptEngine --> LiteLLM[LiteLLM Gateway]
        LiteLLM --> Response([Synthesized Answer & Evidence])
    end
```

---

## ✨ Key Capabilities

- 🖼️ **Multimodal Indexing**: Embeds and indexes images with semantic textual tags into local LanceDB disk storage.
- 🔍 **Zero-Shot Visual Retrieval**: Retrieve relevant visual memories using natural language queries via joint CLIP embedding space.
- 🧠 **Context-Aware Reasoning**: Synthesizes answers based on retrieved visual evidence using any model supported by LiteLLM (Gemini, Claude, GPT, Ollama).
- 🛡️ **Resilient Fallbacks**: Runs with full hardware acceleration when PyTorch & CUDA are available, or in lightweight fallback mode for low-resource environments.

---

## 🚀 Getting Started

### 1. Installation

```bash
git clone https://github.com/NezerkC/vision-cognitive-agent.git
cd vision-cognitive-agent
pip install -r requirements.txt
```

### 2. CLI Usage

#### Index an Image into Visual Memory
```bash
python main.py index ./assets/diagram.png --label "Microservices architecture diagram showing auth and database layers"
```

#### Recall Visual Memories by Query
```bash
python main.py recall "database architecture" --limit 3
```

#### Ask Questions to the Cognitive Agent
```bash
python main.py ask "Which service connects directly to the database?"
```

---

## 🐍 Python API Usage

```python
from vision_agent.agent import VisionCognitiveAgent

# Initialize agent
agent = VisionCognitiveAgent()

# Store an episodic visual memory
mem_id = agent.remember_image(
    image_path="screenshot.png",
    label="Server dashboard displaying 99.9% uptime"
)

# Recall relevant visual evidence
memories = agent.recall("uptime metrics", limit=2)

# Ask questions over visual context
answer = agent.answer_query("What is the current server status?")
print(answer)
```

---

## 🧪 Testing

Run the test suite:

```bash
python -m unittest discover -s tests
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
