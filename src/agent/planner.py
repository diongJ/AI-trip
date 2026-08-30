from __future__ import annotations

import json
from typing import Protocol

from src.agent.models import QuestionType, RouteDecision, ToolName
from src.config.settings import Settings

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    httpx = None


class QueryPlanner(Protocol):
    def plan(self, question: str, fallback: RouteDecision) -> RouteDecision: ...


class DeepSeekQueryPlanner:
    """Create a bounded multi-query plan without adding another model service."""

    def __init__(self, settings: Settings, *, http_client: object | None = None) -> None:
        if httpx is None:
            raise RuntimeError("httpx is required for DeepSeek query planning")
        settings.require_deepseek()
        self.settings = settings
        self._owns_client = http_client is None
        self.client = http_client or httpx.Client(timeout=settings.deepseek_timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def plan(self, question: str, fallback: RouteDecision) -> RouteDecision:
        payload = {
            "model": self.settings.deepseek_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是南越专题检索规划器。范围包括南越王博物院、南越国历史、考古、"
                        "文物工艺、汉代背景和文化交流；不包括实时客流、天气、餐饮、交通或任意百科。"
                        "只输出JSON，字段为intent、entities、subqueries、relations、scope、tool、reason。"
                        "subqueries必须恰好包含3个简短中文检索式；scope只能是in_scope或out_of_scope；"
                        "tool只能是search_kg、search_documents、hybrid_search或none。"
                    ),
                },
                {"role": "user", "content": question},
            ],
            "thinking": {"type": "disabled"},
            "temperature": 0,
            "max_tokens": 320,
            "response_format": {"type": "json_object"},
        }
        try:
            response = self.client.post(
                f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.deepseek_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            raw = json.loads(response.json()["choices"][0]["message"]["content"])
            scope = raw.get("scope", "in_scope")
            tool = ToolName(raw.get("tool", fallback.tool.value))
            subqueries = [str(item).strip() for item in raw.get("subqueries", []) if str(item).strip()]
            subqueries = list(dict.fromkeys([question, *subqueries]))[:4]
            # The deterministic router owns scope safety. The model may enrich
            # a valid route, but cannot reject it before local retrieval and
            # the evidence-backed fallback have had a chance to run.
            if fallback.scope == "in_scope" and (scope == "out_of_scope" or tool == ToolName.NONE):
                return fallback.model_copy(update={"subqueries": subqueries or fallback.subqueries})
            if scope == "out_of_scope":
                tool = ToolName.NONE
            entities = [str(item).strip() for item in raw.get("entities", []) if str(item).strip()]
            return RouteDecision(
                question_type=_question_type(str(raw.get("intent", fallback.intent)), tool),
                tool=tool,
                reason=str(raw.get("reason") or fallback.reason),
                entity_query=entities[0] if entities else fallback.entity_query,
                intent=str(raw.get("intent") or fallback.intent),
                entities=entities,
                subqueries=subqueries,
                relations=[str(item).strip() for item in raw.get("relations", []) if str(item).strip()],
                scope=scope,
                answer_mode=fallback.answer_mode,
                temporal_scope=fallback.temporal_scope,
                as_of=fallback.as_of,
                visit_zone=fallback.visit_zone,
            )
        except Exception:
            return fallback.model_copy(update={"subqueries": fallback.subqueries or [question]})


def _question_type(intent: str, tool: ToolName) -> QuestionType:
    if tool == ToolName.NONE:
        return QuestionType.OUT_OF_SCOPE
    if intent in {"entity_fact", "fact"}:
        return QuestionType.ENTITY_FACT
    if intent in {"relation", "relation_exploration", "comparison"}:
        return QuestionType.RELATION_EXPLORATION
    return QuestionType.DESCRIPTION
