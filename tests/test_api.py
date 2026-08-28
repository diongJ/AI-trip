from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import create_app
from src.agent.models import AnswerStatus


class FakeRuntime:
    status = SimpleNamespace(
        corpus_ready=True,
        graph_ready=True,
        deepseek_configured=False,
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
    assert client.get("/api/health").json()["fallback_mode"] is True
    assert client.get("/api/stats").json()["documents"] == 220
    payload = client.post("/api/ask", json={"question": "南越文王墓"}).json()
    assert payload["response_status"] == "insufficient_evidence"
    assert payload["suggested_questions"]
