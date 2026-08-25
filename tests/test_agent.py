from pathlib import Path
import json

from src.extraction.models import Entity, ExtractionResult, Relation
from src.agent.models import QuestionType, ToolName
from src.agent.router import RuleBasedRouter
from src.agent.service import AgentService
from src.agent.tools import AgentTools
from src.rag.models import DocumentChunk
from src.rag.retriever import RagRetriever

from src.rag.index import build_rag_index
from src.graph.retriever import LocalGraphRetriever


def build_tools(tmp_path) -> AgentTools:
    corpus = tmp_path / "raw"
    index = tmp_path / "index"
    graph_path = tmp_path / "graph.json"
    write_doc(corpus, "DOC_005", "南越文王墓墓主人身份", "person", "墓主人是南越国第二代王赵眜，自称南越文帝。")
    write_doc(corpus, "DOC_013", "文帝行玺", "relic", "文帝行玺是南越文王墓出土的金印，印面阴刻小篆文字。")
    build_rag_index(corpus_root=corpus, index_dir=index, force=True, chunk_size=120)
    write_test_graph(Path(graph_path))
    return AgentTools(
        document_retriever=RagRetriever(index),
        graph_retriever=LocalGraphRetriever(graph_path),
    )


def write_doc(root, doc_id: str, title: str, category: str, text: str) -> None:
    path = root / category / f"{doc_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "doc_id": doc_id,
                "title": title,
                "source_name": "南越王博物院",
                "source_url": "https://www.nywmuseum.org.cn/",
                "source_type": "official",
                "category": category,
                "retrieved_at": "2026-08-23",
                "text": text,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def write_test_graph(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = ExtractionResult(
        entities=[
            Entity(
                id="person:赵眜",
                name="赵眜",
                type="Person",
                aliases=["南越文王"],
                source_ids=["DOC_005"],
                confidence=0.95,
            ),
            Entity(
                id="relic:文帝行玺",
                name="文帝行玺",
                type="Relic",
                aliases=["文帝行玺金印"],
                source_ids=["DOC_013"],
                confidence=0.95,
            ),
            Entity(
                id="material:金",
                name="金",
                type="Material",
                aliases=[],
                source_ids=["DOC_013"],
                confidence=0.95,
            ),
        ],
        relations=[
            Relation(
                source_id="relic:文帝行玺",
                relation="MADE_OF",
                target_id="material:金",
                document_id="DOC_013",
                evidence="文帝行玺为金印。",
                confidence=0.95,
            )
        ],
    )
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def test_router_prefers_kg_for_entity_relation_question(tmp_path) -> None:
    tools = build_tools(tmp_path)
    route = RuleBasedRouter(tools.graph_retriever).route("文帝行玺是什么材料？")

    assert route.question_type == QuestionType.RELATION_EXPLORATION
    assert route.tool == ToolName.SEARCH_KG
    assert route.entity_query == "文帝行玺是什么材料"


def test_agent_returns_grounded_answer_with_citations(tmp_path) -> None:
    service = AgentService(build_tools(tmp_path))

    answer = service.answer("文帝行玺是什么材料？")

    assert not answer.insufficient_evidence
    assert answer.citations
    assert answer.used_tools == [ToolName.SEARCH_KG]
    assert any(citation.doc_id == "DOC_013" for citation in answer.citations)
    assert {fact.relation for fact in answer.graph_facts} == {"MADE_OF"}
    assert "金" in answer.answer


def test_agent_refuses_out_of_scope_realtime_question(tmp_path) -> None:
    service = AgentService(build_tools(tmp_path))

    answer = service.answer("今天馆内有多少游客？")

    assert answer.insufficient_evidence
    assert answer.citations == []
    assert answer.used_tools == []


def test_agent_refuses_obvious_false_location_premise(tmp_path) -> None:
    service = AgentService(build_tools(tmp_path))

    answer = service.answer("火星上的南越王墓是谁建的？")

    assert answer.insufficient_evidence
    assert answer.citations == []
    assert answer.used_tools == []


def test_router_uses_hybrid_when_document_evidence_is_requested(tmp_path) -> None:
    tools = build_tools(tmp_path)

    route = RuleBasedRouter(tools.graph_retriever).route("赵眜是谁？请结合文物证据。")

    assert route.tool == ToolName.HYBRID_SEARCH


def test_agent_uses_document_search_for_descriptive_question(tmp_path) -> None:
    service = AgentService(build_tools(tmp_path))

    answer = service.answer("介绍一下文帝行玺")

    assert not answer.insufficient_evidence
    assert answer.used_tools == [ToolName.HYBRID_SEARCH]
    assert answer.citations


def test_document_chunk_import_remains_available() -> None:
    assert DocumentChunk.__name__ == "DocumentChunk"
