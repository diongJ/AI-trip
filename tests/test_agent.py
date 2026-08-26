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
    write_doc(
        corpus,
        "DOC_153",
        "王墓展区参观基础信息",
        "tourism",
        "南越王博物院王墓展区位于广州市越秀区解放北路867号，周二至周日9:00-17:30开放，南越文王墓墓室下层参观票需另行预约。",
    )
    write_doc(
        corpus,
        "DOC_155",
        "王墓展区重点文物速览",
        "tourism",
        "王墓展区适合重点观看文帝行玺、丝缕玉衣、角形玉杯和船纹铜提筒，按墓主身份、墓葬结构和代表文物组织游览。",
    )
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
    assert route.entity_query == "文帝行玺"


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


def test_router_allows_stable_visit_guidance(tmp_path) -> None:
    tools = build_tools(tmp_path)

    route = RuleBasedRouter(tools.graph_retriever).route("王墓展区开放时间和预约怎么安排？")

    assert route.tool == ToolName.SEARCH_DOCUMENTS
    assert route.intent == "visit_guidance"


def test_agent_answers_visit_guidance_with_citations(tmp_path) -> None:
    service = AgentService(build_tools(tmp_path))

    answer = service.answer("南越王博物院王墓展区怎么玩？")

    assert not answer.insufficient_evidence
    assert answer.used_tools == [ToolName.SEARCH_DOCUMENTS]
    assert answer.citations
    assert "王墓展区" in answer.answer


def test_agent_keeps_realtime_visit_questions_out_of_scope(tmp_path) -> None:
    service = AgentService(build_tools(tmp_path))

    answer = service.answer("今天王墓展区还剩多少预约名额？")

    assert answer.insufficient_evidence
    assert answer.citations == []
    assert answer.used_tools == []


def test_agent_can_use_deepseek_fallback_when_local_evidence_is_missing(tmp_path) -> None:
    class EmptyDocumentRetriever:
        def search(self, query, *, top_k=5, category=None, min_score=0.0):
            return []

        def search_many(self, queries, *, top_k=8, per_query_k=12, category=None, source_tier=None):
            return []

    class EmptyGraphRetriever:
        def list_entities(self, query="", *, entity_type=None, limit=100):
            return []

        def resolve_entity_id(self, query):
            return None

        def get_neighbors(self, entity_query, *, depth=1, limit=20):
            return []

    class FakeFallback:
        def __init__(self) -> None:
            self.calls = 0

        def generate_without_evidence(self, question, route):
            self.calls += 1
            return f"本地知识库未检索到可引用证据，以下为 DeepSeek 通用回答：{question}"

    fallback = FakeFallback()
    service = AgentService(
        AgentTools(
            document_retriever=EmptyDocumentRetriever(),
            graph_retriever=EmptyGraphRetriever(),
        ),
        fallback_generator=fallback,
    )

    answer = service.answer("南越王博物院和广州城市史有什么联系？")

    assert answer.insufficient_evidence
    assert answer.citations == []
    assert fallback.calls == 1
    assert "DeepSeek 通用回答" in answer.answer


def test_agent_does_not_use_deepseek_fallback_for_out_of_scope_realtime(tmp_path) -> None:
    class FakeFallback:
        def generate_without_evidence(self, question, route):  # pragma: no cover - must not run
            raise AssertionError("fallback should not be called for out-of-scope questions")

    service = AgentService(build_tools(tmp_path), fallback_generator=FakeFallback())

    answer = service.answer("今天馆内有多少游客？")

    assert answer.insufficient_evidence
    assert answer.used_tools == []


def test_document_chunk_import_remains_available() -> None:
    assert DocumentChunk.__name__ == "DocumentChunk"


def test_search_kg_drops_offtopic_neighbors(tmp_path) -> None:
    # 命中实体但问的是语料外方面（赋税制度）时，不得把所有邻居关系当答案倒出。
    tools = build_tools(tmp_path)

    result = tools.search_kg("文帝行玺和秦朝的赋税制度有何异同？", entity_query="文帝行玺")

    assert result.graph == []


def test_search_kg_keeps_neighbors_for_plain_entity_question(tmp_path) -> None:
    # 纯实体提问（无具体方面词）时，邻居关系全部保留。
    tools = build_tools(tmp_path)

    result = tools.search_kg("介绍一下文帝行玺", entity_query="文帝行玺")

    assert result.graph


def test_agent_refuses_unknown_person_instead_of_near_name_answer(tmp_path) -> None:
    # “赵高”不在知识库中，不得因同姓就拿赵佗/赵眜的资料冒充答案。
    service = AgentService(build_tools(tmp_path))

    answer = service.answer("赵高是谁？")

    assert answer.insufficient_evidence
    assert answer.citations == []
    assert "赵高" in answer.answer
    # 允许以“你或许想了解”的形式建议相近实体，但不允许直接当成答案。
    assert "你或许想了解" in answer.answer


def test_agent_still_answers_known_subject_after_unknown_focus_guard(tmp_path) -> None:
    # 知识库收录的主题不得被未知主题闸门误伤。
    service = AgentService(build_tools(tmp_path))

    answer = service.answer("文帝行玺是什么材料？")

    assert not answer.insufficient_evidence
    assert "金" in answer.answer


def test_agent_downgrades_answer_that_does_not_match_evidence(tmp_path) -> None:
    # 生成器选出合法证据 ID 但答案内容与证据毫无重叠时，必须降级为证据不足。
    from src.agent.context import graph_evidence_id
    from src.agent.models import GeneratedAnswer

    class HallucinatingGenerator:
        def generate(self, question, route, result):
            return GeneratedAnswer(
                answer="该文物由外星文明用纳米技术制造而成。",
                selected_evidence_ids=[graph_evidence_id(result.graph[0])],
            )

    service = AgentService(build_tools(tmp_path), generator=HallucinatingGenerator())

    answer = service.answer("文帝行玺是什么材料？")

    assert answer.insufficient_evidence
    assert answer.citations == []
    assert answer.refusal_reason == "生成答案与所选证据一致性不足"


def test_agent_keeps_grounded_answer_after_faithfulness_check(tmp_path) -> None:
    # 与证据一致的正常答案不得被忠实度校验误伤。
    service = AgentService(build_tools(tmp_path))

    answer = service.answer("文帝行玺是什么材料？")

    assert not answer.insufficient_evidence
    assert "金" in answer.answer
