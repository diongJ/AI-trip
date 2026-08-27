import json
from hashlib import sha256

import httpx
import pytest

from src.agent.models import QuestionType, RouteDecision, ToolName
from src.agent.planner import DeepSeekQueryPlanner
from src.agent.service import AnswerGenerationError, DeepSeekWebSearchAnswerGenerator
from src.config.settings import Settings
from src.preprocessing import CorpusDocument
from src.preprocessing.sources import sync_sources
from src.rag.index import BM25_BACKEND, build_rag_index
from src.rag.retriever import RagRetriever


def _settings() -> Settings:
    return Settings(_env_file=None, deepseek_api_key="test-secret")


def _write_doc(root, doc_id: str, title: str, text: str, *, tier: str = "core") -> None:
    path = root / "history" / f"{doc_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "doc_id": doc_id,
                "title": title,
                "source_name": "测试来源",
                "source_url": f"https://example.org/{doc_id}",
                "source_type": "official",
                "category": "history",
                "retrieved_at": "2026-08-26",
                "text": text,
                "source_tier": tier,
                "topic_tags": ["南越国"],
                "evidence_role": "factual",
                "content_hash": sha256(text.encode("utf-8")).hexdigest(),
                "review_status": "approved",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_corpus_requires_persisted_hash_and_rejects_wrong_hash() -> None:
    text = "南越国是秦汉时期岭南历史的重要组成部分。"
    payload = {
        "doc_id": "DOC_100",
        "title": "南越国历史",
        "source_name": "测试来源",
        "source_url": "https://example.org/doc",
        "source_type": "official",
        "category": "history",
        "retrieved_at": "2026-08-26",
        "text": text,
        "evidence_role": "factual",
        "content_hash": sha256(text.encode("utf-8")).hexdigest(),
        "review_status": "approved",
    }
    document = CorpusDocument.model_validate(payload)
    assert len(document.content_hash) == 64
    missing_hash = {key: value for key, value in payload.items() if key != "content_hash"}
    with pytest.raises(ValueError, match="content_hash"):
        CorpusDocument.model_validate(missing_hash)
    with pytest.raises(ValueError, match="content_hash"):
        CorpusDocument.model_validate({**payload, "content_hash": "bad"})


def test_bm25_multi_query_fusion_and_source_tier(tmp_path) -> None:
    corpus = tmp_path / "raw"
    index = tmp_path / "index"
    _write_doc(corpus, "DOC_100", "番禺与南越国都城", "秦汉时期番禺是南越国都城，也是岭南重要政治中心。")
    _write_doc(corpus, "DOC_101", "南越宫署遗址", "南越国宫署遗址保存宫殿和园林遗迹，是重要考古发现。", tier="extended")
    manifest = build_rag_index(corpus_root=corpus, index_dir=index, force=True)
    retriever = RagRetriever(index)

    hits = retriever.search_many(["南越国首都", "番禺都城"], top_k=2)

    assert manifest["embedding_model"] == BM25_BACKEND
    assert hits[0].metadata["doc_id"] == "DOC_100"
    assert 0 < hits[0].metadata["fusion_score"] <= 1
    assert retriever.search("宫署遗址", source_tier="extended")[0].metadata["doc_id"] == "DOC_101"


def test_deepseek_planner_returns_structured_multi_query_plan() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-secret"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "comparison",
                                    "entities": ["文帝行玺", "丝缕玉衣"],
                                    "subqueries": ["文帝行玺 特征", "丝缕玉衣 特征", "两件文物 比较"],
                                    "relations": ["MADE_OF"],
                                    "scope": "in_scope",
                                    "tool": "hybrid_search",
                                    "reason": "需要比较多件文物",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    fallback = RouteDecision(
        question_type=QuestionType.DESCRIPTION,
        tool=ToolName.SEARCH_DOCUMENTS,
        reason="fallback",
        subqueries=["原问题"],
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        plan = DeepSeekQueryPlanner(_settings(), http_client=client).plan("比较两件文物", fallback)

    assert plan.tool == ToolName.HYBRID_SEARCH
    assert plan.entities == ["文帝行玺", "丝缕玉衣"]
    assert plan.subqueries[0] == "比较两件文物"
    assert len(plan.subqueries) == 4


def test_deepseek_web_search_requires_real_search_and_traceable_source() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/responses"
        assert payload["model"] == "deepseek-v4-flash"
        assert payload["tools"] == [{"type": "web_search"}]
        assert payload["tool_choice"] == {"type": "web_search"}
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "web_search_call",
                        "status": "completed",
                        "action": {"type": "open_page", "url": "https://museum.example/source"},
                    },
                    {
                        "type": "message",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "联网资料显示该问题仍需结合馆方研究判断。",
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "title": "测试博物馆资料",
                                        "url": "https://museum.example/source",
                                    }
                                ],
                            }
                        ],
                    },
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = DeepSeekWebSearchAnswerGenerator(
            _settings(), http_client=client
        ).search("南越国某项制度是什么？")

    assert "联网资料" in result.answer
    assert len(result.sources) == 1
    assert str(result.sources[0].url) == "https://museum.example/source"


def test_deepseek_web_search_rejects_untraceable_answer() -> None:
    response = httpx.Response(
        200,
        json={
            "output": [
                {"type": "web_search_call", "status": "completed", "action": {"type": "search", "query": "南越"}},
                {"type": "message", "content": [{"type": "output_text", "text": "没有来源的答案"}]},
            ]
        },
    )

    with httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client:
        with pytest.raises(AnswerGenerationError, match="traceable source"):
            DeepSeekWebSearchAnswerGenerator(_settings(), http_client=client).search("南越问题")


def test_whitelist_sync_accepts_relevant_pages_and_deduplicates(tmp_path) -> None:
    config = tmp_path / "sources.json"
    output = tmp_path / "raw" / "extended"
    config.write_text(
        json.dumps(
            {
                "relevance_keywords": ["南越", "考古", "文物"],
                "sources": [
                    {
                        "name": "测试博物馆",
                        "domains": ["museum.example"],
                        "seed_urls": ["https://museum.example/start"],
                        "include_paths": ["^/(start|detail)"],
                        "source_type": "official",
                        "source_tier": "extended",
                            "review_status": "approved",
                            "follow_links": True,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    page = "南越考古文物" * 70

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(200, text=f"<html><title>南越专题</title><a href='/detail'>详情</a><p>{page}</p></html>", headers={"content-type": "text/html"})
        return httpx.Response(200, text=f"<html><title>重复页</title><p>{page}</p></html>", headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = sync_sources(config, output_root=output, max_pages=5, http_client=client)

    assert report.accepted == 1
    assert report.rejected_duplicate == 1
    assert len(list(output.rglob("*.json"))) == 1
