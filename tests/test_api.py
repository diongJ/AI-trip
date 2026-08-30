from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import create_app
from src.agent.models import AnswerStatus


class FakeRuntime:
    status = SimpleNamespace(
        corpus_ready=True,
        rag_ready=True,
        graph_ready=True,
        semantic_ready=False,
        deepseek_configured=False,
        web_search_configured=False,
        neo4j_configured=False,
        document_count=220,
        entity_count=78,
        relation_count=87,
    )

    def ask(self, question, **_kwargs):
        response = SimpleNamespace(
            answer=f"关于{question}的可追溯回答",
            citations=[],
            web_sources=[],
            route_reason="测试路由",
            used_tools=[],
            insufficient_evidence=True,
            response_status=AnswerStatus.INSUFFICIENT_EVIDENCE,
            suggested_questions=["南越文王墓为什么重要？"],
        )
        return SimpleNamespace(response=response, generation_mode="离线证据摘录", warning=None, elapsed_ms=1.2)

    def list_entities(self, *_args, **_kwargs):
        return []


def test_api_health_stats_and_ask():
    client = TestClient(create_app(runtime_provider=FakeRuntime))
    health = client.get("/api/health").json()
    assert health["fallback_mode"] is True
    assert health["rag_ready"] is True
    assert health["semantic_ready"] is False
    assert health["release"]
    assert client.get("/api/stats").json()["documents"] == 220
    payload = client.post("/api/ask", json={"question": "南越文王墓"}).json()
    assert payload["response_status"] == "insufficient_evidence"
    assert payload["suggested_questions"]


def test_api_limits_public_questions_without_losing_other_routes():
    client = TestClient(create_app(runtime_provider=FakeRuntime, rate_limit_per_minute=1))
    headers = {"X-Forwarded-For": "203.0.113.10"}
    assert client.post("/api/ask", json={"question": "南越文王墓"}, headers=headers).status_code == 200
    limited = client.post("/api/ask", json={"question": "赵眜是谁"}, headers=headers)
    assert limited.status_code == 429
    assert limited.headers["retry-after"]
    assert "频繁" in limited.json()["detail"]
    assert client.post("/api/ask", json={"question": "赵眜是谁"}, headers={"X-Forwarded-For": "203.0.113.11"}).status_code == 200
    assert client.get("/api/stats").status_code == 200


def test_api_serves_static_files_and_spa_routes(tmp_path: Path):
    static_dir = tmp_path / "dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>museum</html>", encoding="utf-8")
    (static_dir / "asset.txt").write_text("asset", encoding="utf-8")
    client = TestClient(create_app(runtime_provider=FakeRuntime, static_dir=static_dir))
    assert client.get("/").text == "<html>museum</html>"
    assert client.get("/asset.txt").text == "asset"
    assert client.get("/relic/wendi-seal").text == "<html>museum</html>"
    assert client.get("/api/not-found").status_code == 404
