"""CLI Entry point for Vision Cognitive Agent."""

import argparse
import sys
import logging
from vision_agent.agent import VisionCognitiveAgent
from vision_agent.config import AgentConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    parser = argparse.ArgumentParser(description="Vision Cognitive Agent CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Index command
    index_parser = subparsers.add_parser("index", help="Index an image into visual memory")
    index_parser.add_argument("image_path", type=str, help="Path to the image file")
    index_parser.add_argument("--label", type=str, required=True, help="Description or label for the image")

    # Recall command
    recall_parser = subparsers.add_parser("recall", help="Search visual memories by text query")
    recall_parser.add_argument("query", type=str, help="Text query to search for")
    recall_parser.add_argument("--limit", type=int, default=3, help="Number of memories to recall")

    # Ask command
    ask_parser = subparsers.add_parser("ask", help="Ask a question about the stored visual memories")
    ask_parser.add_argument("question", type=str, help="Question to ask the cognitive agent")

    args = parser.parse_args()

    agent = VisionCognitiveAgent()

    if args.command == "index":
        mem_id = agent.remember_image(args.image_path, args.label)
        print(f"✅ Memory indexed successfully with ID: {mem_id}")
    elif args.command == "recall":
        results = agent.recall(args.query, limit=args.limit)
        print(f"\n🔍 Recalled {len(results)} visual memories for: '{args.query}'")
        for r in results:
            print(f" - [{r.get('id')}] {r.get('label')} (score: {r.get('_score', 'N/A')})")
    elif args.command == "ask":
        answer = agent.answer_query(args.question)
        print(f"\n🤖 Agent Response:\n{answer}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
