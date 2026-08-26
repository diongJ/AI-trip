from __future__ import annotations

import argparse

from scripts.verify_retrieval import _ensure_local_graph
from src.agent.service import AgentService, DeepSeekAnswerGenerator, ExtractiveAnswerGenerator
from src.agent.planner import DeepSeekQueryPlanner
from src.agent.tools import AgentTools
from src.config import get_settings
from src.config.settings import ConfigurationError
from src.graph.retriever import LocalGraphRetriever
from src.rag.index import build_rag_index
from src.rag.retriever import RagIndexError, RagRetriever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask a grounded question with Day 5 Agent MVP.")
    parser.add_argument("question")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="use DeepSeek for answer wording; default uses offline extractive answers",
    )
    parser.add_argument("--rebuild-index", action="store_true")
    parser.add_argument("--json", action="store_true", help="print the full JSON response")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_rag_index(force=args.rebuild_index)
    _ensure_local_graph()
    try:
        document_retriever = RagRetriever()
    except RagIndexError:
        build_rag_index(force=True)
        document_retriever = RagRetriever()
    tools = AgentTools(
        document_retriever=document_retriever,
        graph_retriever=LocalGraphRetriever(),
    )
    generator = ExtractiveAnswerGenerator()
    planner = None
    if args.llm:
        try:
            generator = DeepSeekAnswerGenerator(get_settings())
            planner = DeepSeekQueryPlanner(get_settings())
        except ConfigurationError as exc:
            raise SystemExit(f"Cannot use --llm: {exc}") from None

    response = AgentService(tools, generator=generator, planner=planner).answer(args.question)
    if args.json:
        print(response.model_dump_json(indent=2))
        return

    print(response.answer)
    if response.citations:
        print("\n来源：")
        for citation in response.citations:
            print(f"- {citation.doc_id} {citation.title}: {citation.source_url}")


if __name__ == "__main__":
    main()
