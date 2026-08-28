from __future__ import annotations

from collections import Counter
import csv
from pathlib import Path

from src.agent.router import RuleBasedRouter
from src.agent.service import AgentService, ExtractiveAnswerGenerator
from src.agent.tools import AgentTools
from src.graph.retriever import LocalGraphRetriever
from src.preprocessing import load_corpus
from src.rag.index import build_rag_index
from src.rag.retriever import RagRetriever


class EmptyGraphRetriever:
    def list_entities(self, query: str = "", *, entity_type: str | None = None, limit: int = 100):
        return []

    def resolve_entity_id(self, query: str) -> str | None:
        return None

    def get_neighbors(self, entity_query: str, *, depth: int = 1, limit: int = 20):
        return []


def _retriever(tmp_path) -> RagRetriever:
    index_dir = tmp_path / "rag"
    build_rag_index(index_dir=index_dir, force=True)
    return RagRetriever(index_dir=index_dir)


def test_visitor_corpus_has_roles_and_temporal_metadata() -> None:
    corpus = load_corpus()
    assert len(corpus) == 210
    assert Counter(document.evidence_role for document in corpus) == {
        "factual": 180,
        "curated_guidance": 30,
    }
    doc_238 = next(document for document in corpus if document.doc_id == "DOC_238")
    doc_256 = next(document for document in corpus if document.doc_id == "DOC_256")
    assert (doc_238.effective_from, doc_238.effective_until, doc_238.volatility) == (
        "2025-10-09",
        "2025-12-16",
        "expired",
    )
    assert doc_256.evidence_role == "curated_guidance"
    assert doc_256.zone == "两展区"


def test_visitor_faq_regression_inventory_references_valid_documents() -> None:
    with Path("docs/visitor_guidance/visitor_faq.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    known_ids = {document.doc_id for document in load_corpus()}
    # The imported collection currently contains 64 rows (the delivery note
    # says 63); keep every teammate-authored FAQ and guard the promised floor.
    assert len(rows) >= 63
    referenced = {
        doc_id
        for row in rows
        for doc_id in row["关联文档"].split("/")
        if doc_id.startswith("DOC_")
    }
    assert referenced <= known_ids


def test_temporal_retrieval_excludes_expired_current_notices(tmp_path) -> None:
    retriever = _retriever(tmp_path)
    current = retriever.search(
        "墓原址暂停开放",
        top_k=8,
        category="tourism",
        temporal_scope="current",
        zones={"王墓展区", "两展区"},
    )
    historical = retriever.search(
        "墓原址暂停开放",
        top_k=8,
        category="tourism",
        temporal_scope="historical",
        as_of="2025-10-10",
        zones={"王墓展区"},
    )
    assert "DOC_238" not in {hit.metadata["doc_id"] for hit in current}
    assert "DOC_238" in {hit.metadata["doc_id"] for hit in historical}


def test_future_rule_and_cross_zone_route_are_explicit(tmp_path) -> None:
    retriever = _retriever(tmp_path)
    future = retriever.search(
        "讲解研学活动申请",
        top_k=8,
        category="tourism",
        temporal_scope="future",
        as_of="2026-09-01",
        zones={"两展区"},
    )
    assert "DOC_241" in {hit.metadata["doc_id"] for hit in future}

    router = RuleBasedRouter()
    cross_zone = router.route("王墓和王宫怎样联动参观？")
    palace_only = router.route("王宫展区怎么参观？")
    uncertain = router.route("王墓展区可以拍照吗？")
    assert cross_zone.visit_zone.value == "cross_zone"
    assert palace_only.intent == "wanggong_visit_out_of_scope"
    assert uncertain.intent == "visit_uncertain"


def test_cross_zone_project_route_keeps_its_non_official_label(tmp_path) -> None:
    retriever = _retriever(tmp_path)
    result = AgentTools(retriever, EmptyGraphRetriever()).search_documents(
        "王墓和王宫怎样联动参观？",
        category="tourism",
        include_curated_guidance=True,
        temporal_scope="current",
        zones={"王墓展区", "王宫展区", "两展区"},
        top_k=8,
    )
    curated = [hit for hit in result.documents if hit.metadata["evidence_role"] == "curated_guidance"]
    assert curated
    assert all(hit.metadata["doc_id"] != "DOC_238" for hit in result.documents)
    cross_zone_route = next(hit for hit in curated if hit.metadata["doc_id"] == "DOC_256")
    assert "项目整理建议" in cross_zone_route.content


def test_natural_opening_and_route_questions_use_visitor_evidence(tmp_path) -> None:
    retriever = _retriever(tmp_path)
    service = AgentService(
        AgentTools(retriever, EmptyGraphRetriever()),
        generator=ExtractiveAnswerGenerator(),
    )
    opening = service.answer("什么时候开门")
    route = service.answer("最佳游览路线")
    one_hour = service.answer("我只有一小时，怎么安排？")
    family = service.answer("带孩子怎么逛？")
    senior = service.answer("老人怎么参观更省力？")
    assert opening.response_status.value == "answered"
    assert opening.citations
    assert "9:00" in opening.answer
    assert route.response_status.value == "answered"
    assert route.citations
    assert "项目整理建议" in route.answer
    assert {citation.doc_id for citation in route.citations} >= {"DOC_159"}
    assert one_hour.response_status.value == "answered"
    assert {citation.doc_id for citation in one_hour.citations} >= {"DOC_160"}
    assert family.response_status.value == "answered"
    assert {citation.doc_id for citation in family.citations} >= {"DOC_257"}
    assert senior.response_status.value == "answered"
    assert {citation.doc_id for citation in senior.citations} >= {"DOC_259"}


def test_relic_owner_question_resolves_to_the_supported_person_relation(tmp_path) -> None:
    retriever = _retriever(tmp_path)
    service = AgentService(
        AgentTools(retriever, LocalGraphRetriever()),
        generator=ExtractiveAnswerGenerator(),
    )
    answer = service.answer("丝缕玉衣的主人是谁？")
    assert answer.response_status.value == "answered"
    assert "赵眜" in answer.answer
    assert {citation.doc_id for citation in answer.citations} >= {"DOC_007"}
