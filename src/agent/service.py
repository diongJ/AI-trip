from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from src.agent.context import build_grounded_context, citations_from_result, load_source_lookup
from src.agent.models import AgentAnswer, RouteDecision, ToolName, ToolResult
from src.agent.router import RuleBasedRouter
from src.agent.tools import AgentTools
from src.config.settings import ConfigurationError, Settings
from src.preprocessing import CorpusDocument

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - minimal offline installs use extractive mode
    httpx = None


class AnswerGenerationError(RuntimeError):
    pass


class AnswerGenerator(Protocol):
    def generate(self, question: str, route: RouteDecision, result: ToolResult) -> str: ...


class ExtractiveAnswerGenerator:
    def generate(self, question: str, route: RouteDecision, result: ToolResult) -> str:
        if route.tool in {ToolName.SEARCH_DOCUMENTS, ToolName.HYBRID_SEARCH} and result.documents:
            snippets = [hit.content for hit in result.documents[:3]]
            return "\n".join(snippets)
        if result.graph:
            facts = [
                f"{hit.source_entity.name}{_relation_label(hit.relation)}{hit.target_entity.name}。证据：{hit.evidence}"
                for hit in result.graph[:4]
            ]
            return "\n".join(facts)
        if result.documents:
            snippets = [hit.content for hit in result.documents[:3]]
            return "\n".join(snippets)
        return "当前可靠资料不足以确认该问题。"


class DeepSeekAnswerGenerator:
    def __init__(
        self,
        settings: Settings,
        *,
        prompt_path: str | Path = "prompts/grounded_answer.txt",
        http_client: object | None = None,
    ) -> None:
        if httpx is None:
            raise ConfigurationError("httpx is required for DeepSeek answer generation.")
        settings.require_deepseek()
        self.settings = settings
        self.prompt_path = Path(prompt_path)
        self._owns_client = http_client is None
        self.client = http_client or httpx.Client(timeout=45.0)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def generate(self, question: str, route: RouteDecision, result: ToolResult) -> str:
        context = build_grounded_context(result)
        if not context.strip():
            return "当前可靠资料不足以确认该问题。"
        prompt = self.prompt_path.read_text(encoding="utf-8")
        payload = {
            "model": self.settings.deepseek_model,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"问题：{question}\n"
                        f"路由：{route.model_dump_json()}\n\n"
                        f"可用证据：\n{context}"
                    ),
                },
            ],
            "temperature": 0,
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
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(_strip_code_fence(content))
            answer = parsed.get("answer")
            if not isinstance(answer, str) or not answer.strip():
                raise TypeError("answer must be a non-empty string")
            return answer.strip()
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AnswerGenerationError(f"DeepSeek answer generation failed: {exc}") from exc


class AgentService:
    def __init__(
        self,
        tools: AgentTools,
        *,
        router: RuleBasedRouter | None = None,
        generator: AnswerGenerator | None = None,
        source_lookup: dict[str, CorpusDocument] | None = None,
    ) -> None:
        self.tools = tools
        self.router = router or RuleBasedRouter(tools.graph_retriever)
        self.generator = generator or ExtractiveAnswerGenerator()
        self.source_lookup = source_lookup if source_lookup is not None else _safe_source_lookup()

    def answer(self, question: str) -> AgentAnswer:
        route = self.router.route(question)
        if route.tool == ToolName.NONE:
            return AgentAnswer(
                answer="当前可靠资料不足以确认该问题，或问题超出南越王博物院王墓展区资料范围。",
                citations=[],
                used_tools=[],
                route_reason=route.reason,
                insufficient_evidence=True,
            )

        result = self._run_tool(question, route)
        citations = citations_from_result(result, source_lookup=self.source_lookup)
        if not result.has_evidence or not citations:
            return AgentAnswer(
                answer="当前可靠资料不足以确认该问题。",
                citations=[],
                used_tools=[route.tool],
                route_reason=route.reason,
                insufficient_evidence=True,
                retrieved_documents=result.documents,
                graph_facts=result.graph,
            )

        answer_text = self.generator.generate(question, route, result)
        return AgentAnswer(
            answer=answer_text,
            citations=citations,
            used_tools=[route.tool],
            route_reason=route.reason,
            insufficient_evidence=False,
            retrieved_documents=result.documents,
            graph_facts=result.graph,
        )

    def _run_tool(self, question: str, route: RouteDecision) -> ToolResult:
        if route.tool == ToolName.SEARCH_KG:
            return self.tools.search_kg(question, entity_query=route.entity_query)
        if route.tool == ToolName.SEARCH_DOCUMENTS:
            return self.tools.search_documents(question)
        if route.tool == ToolName.HYBRID_SEARCH:
            return self.tools.hybrid_search(question, entity_query=route.entity_query)
        raise ValueError(f"unsupported tool: {route.tool}")


def create_deepseek_generator(settings: Settings) -> DeepSeekAnswerGenerator:
    try:
        return DeepSeekAnswerGenerator(settings)
    except ConfigurationError:
        raise


def _strip_code_fence(content: str) -> str:
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return value


def _relation_label(relation: str) -> str:
    labels = {
        "BELONGS_TO_STATE": "属于",
        "BURIED_IN": "墓葬于",
        "CONTAINS": "包含",
        "EXCAVATED_FROM": "出土于",
        "MADE_OF": "材质为",
        "BELONGS_TO_CATEGORY": "属于类别",
        "CREATED_IN": "制作于",
        "RELATED_TO_PERSON": "关联人物为",
        "REFLECTS_CULTURE": "反映",
        "HAS_PATTERN": "具有纹饰",
        "INVOLVES_PERSON": "涉及人物",
        "OCCURRED_IN": "发生于",
    }
    return labels.get(relation, f" {relation} ")


def _safe_source_lookup() -> dict[str, CorpusDocument]:
    try:
        return load_source_lookup()
    except Exception:
        return {}
