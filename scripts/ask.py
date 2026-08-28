from __future__ import annotations

import argparse

from scripts.verify_retrieval import _ensure_local_graph
from src.agent.service import (
    AgentService,
    DeepSeekAnswerGenerator,
    DeepSeekWebSearchAnswerGenerator,
    ExtractiveAnswerGenerator,
)
from src.agent.planner import DeepSeekQueryPlanner
from src.agent.models import AnswerStatus
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
    web_search_generator = None
    if args.llm:
        try:
            settings = get_settings()
            generator = DeepSeekAnswerGenerator(settings)
            web_search_generator = DeepSeekWebSearchAnswerGenerator(settings)
            planner = DeepSeekQueryPlanner(settings)
        except ConfigurationError as exc:
            raise SystemExit(f"Cannot use --llm: {exc}") from None

    response = AgentService(
        tools,
        generator=generator,
        web_search_generator=web_search_generator,
        planner=planner,
    ).answer(args.question)
    if args.json:
        print(response.model_dump_json(indent=2))
        return

    if response.response_status == AnswerStatus.WEB_SEARCH_ANSWERED:
        print("【DeepSeek 联网搜索补充｜内容未进入本地知识库，请结合来源注意甄别】")
    print(response.answer)
    if response.citations:
        print("\n来源：")
        for citation in response.citations:
            print(f"- {citation.doc_id} {citation.title}: {citation.source_url}")
    if response.web_sources:
        print("\n联网来源（请注意甄别）：")
        for source in response.web_sources:
            print(f"- {source.title}: {source.url}")


if __name__ == "__main__":
    main()
