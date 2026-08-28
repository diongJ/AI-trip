from __future__ import annotations

import re
import time
from dataclasses import dataclass

from src.agent.context import citations_from_result
from src.agent.models import (
    AgentAnswer,
    AnswerMode,
    AnswerStatus,
    Audience,
    Citation,
    ConversationTurn,
    ToolResult,
)
from src.agent.planner import DeepSeekQueryPlanner
from src.agent.service import (
    AgentService,
    AnswerGenerationError,
    DeepSeekAnswerGenerator,
    DeepSeekClaimVerifier,
    DeepSeekWebSearchAnswerGenerator,
    ExtractiveAnswerGenerator,
)
from src.agent.tools import AgentTools
from src.config import Settings, get_settings
from src.config.settings import ConfigurationError
from src.graph.retriever import LocalGraphRetriever
from src.rag.index import build_rag_index
from src.rag.models import GraphEntity, GraphHit
from src.rag.retriever import RagIndexError, RagRetriever
from src.rag.semantic import SemanticRagRetriever, SemanticUnavailable


EXPLANATION_STYLES = {
    "简短导览": "请用约 180 字写一段清晰、适合现场参观的简短导览",
    "深度讲解": "请用约 500 字分层讲解其背景、特征、关系与文化意义",
    "亲子版": "请用约 250 字、适合 8 至 12 岁儿童理解的生动语言讲解，并提出一个观察问题",
}


@dataclass(frozen=True)
class QueryOutcome:
    response: AgentAnswer
    elapsed_ms: float
    generation_mode: str
    warning: str | None = None


@dataclass(frozen=True)
class RuntimeStatus:
    corpus_ready: bool
    rag_ready: bool
    graph_ready: bool
    semantic_ready: bool
    deepseek_configured: bool
    web_search_configured: bool
    neo4j_configured: bool
    document_count: int
    entity_count: int
    relation_count: int


class AppRuntime:
    """Cached, read-only application services shared by Streamlit pages."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        manifest = build_rag_index()
        try:
            rag = RagRetriever()
        except RagIndexError:
            build_rag_index(force=True)
            rag = RagRetriever()
        semantic_ready = False
        semantic_warning: str | None = None
        document_retriever = rag
        if self.settings.semantic_retrieval_enabled:
            try:
                document_retriever = SemanticRagRetriever(
                    rag,
                    embedding_model=self.settings.semantic_embedding_model,
                    reranker_model=self.settings.semantic_reranker_model,
                )
                semantic_ready = document_retriever.available
            except SemanticUnavailable:
                semantic_warning = "本地语义检索未安装，已使用 BM25 检索。"
        self.graph = LocalGraphRetriever()
        tools = AgentTools(document_retriever=document_retriever, graph_retriever=self.graph)
        self.extractive_service = AgentService(
            tools,
            generator=ExtractiveAnswerGenerator(),
        )
        self.deepseek_service: AgentService | None = None
        self._deepseek_setup_warning: str | None = None
        self._semantic_setup_warning = semantic_warning
        try:
            self.deepseek_service = AgentService(
                tools,
                generator=DeepSeekAnswerGenerator(self.settings),
                web_search_generator=DeepSeekWebSearchAnswerGenerator(self.settings),
                claim_verifier=DeepSeekClaimVerifier(self.settings),
                planner=DeepSeekQueryPlanner(self.settings),
            )
        except ConfigurationError:
            self._deepseek_setup_warning = (
                "DeepSeek 未配置，已使用离线证据摘录模式。"
            )

        self.status = RuntimeStatus(
            corpus_ready=bool(rag.chunks),
            rag_ready=True,
            graph_ready=bool(self.graph.entities),
            semantic_ready=semantic_ready,
            deepseek_configured=self.deepseek_service is not None,
            web_search_configured=self.deepseek_service is not None,
            neo4j_configured=_neo4j_is_configured(self.settings),
            document_count=int(manifest.get("document_count", 0)),
            entity_count=len(self.graph.entities),
            relation_count=len(self.graph.relations),
        )

    def ask(
        self,
        question: str,
        *,
        history: list[ConversationTurn] | None = None,
        answer_mode: AnswerMode = AnswerMode.AUTO,
        prefer_llm: bool = True,
        audience: Audience = Audience.ADULT,
    ) -> QueryOutcome:
        started = time.perf_counter()
        warning = None
        mode = "离线证据摘录"
        if audience == Audience.KIDS:
            # 儿童模式固定走离线证据生成：确定性、可追溯、不会答偏。
            # DeepSeek 叙事化生成对儿童短句的接地校验不稳定，待提示词
            # 调优后再按需启用。
            response = _ask_service(self.extractive_service, question, history, answer_mode, audience)
            mode = "小越离线故事"
            if prefer_llm:
                warning = self._deepseek_setup_warning or self._semantic_setup_warning
        elif prefer_llm and self.deepseek_service is not None:
            try:
                response = _ask_service(self.deepseek_service, question, history, answer_mode, audience)
                mode = "DeepSeek 证据综合" if response.claims_verified else "DeepSeek 智能生成"
            except AnswerGenerationError:
                response = _ask_service(self.extractive_service, question, history, answer_mode, audience)
                warning = "智能生成服务暂时不可用，本次已回退到离线证据摘录。"
        else:
            response = _ask_service(self.extractive_service, question, history, answer_mode, audience)
            if prefer_llm:
                warning = self._deepseek_setup_warning or self._semantic_setup_warning
        if response.response_status == AnswerStatus.WEB_SEARCH_ANSWERED:
            mode = "DeepSeek 联网搜索"
        elif response.response_status == AnswerStatus.CHAT:
            mode = "小越聊天"
        elif response.insufficient_evidence:
            mode = "规则拒答 / 证据不足"
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        return QueryOutcome(
            response=response,
            elapsed_ms=elapsed_ms,
            generation_mode=mode,
            warning=warning,
        )

    def list_entities(
        self,
        query: str = "",
        *,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[GraphEntity]:
        return self.graph.list_entities(
            query,
            entity_type=entity_type,
            limit=limit,
        )

    def neighbors(self, entity_name: str, *, limit: int = 30) -> list[GraphHit]:
        return self.graph.get_neighbors(entity_name, depth=1, limit=limit)

    def citation_for_graph_hit(self, hit: GraphHit) -> Citation | None:
        citations = citations_from_result(
            ToolResult(graph=[hit]),
            source_lookup=self.extractive_service.source_lookup,
        )
        return citations[0] if citations else None


def build_explanation_prompt(entity_name: str, style: str) -> str:
    instruction = EXPLANATION_STYLES.get(style)
    if instruction is None:
        raise ValueError(f"unsupported explanation style: {style}")
    return (
        f"介绍一下{entity_name}。{instruction}。"
        "请结合文物证据说明，所有判断必须来自当前王墓展区可靠资料。"
    )


def explanation_markdown(entity_name: str, style: str, outcome: QueryOutcome) -> str:
    lines = [
        f"# {entity_name}｜{style}",
        "",
        outcome.response.answer,
        "",
        "## 参考来源",
        "",
    ]
    if not outcome.response.citations:
        lines.append("当前可靠资料不足，未生成可引用来源。")
    for citation in outcome.response.citations:
        lines.extend(
            [
                f"- **{citation.doc_id}｜{citation.title}**",
                f"  - 来源：{citation.source_name}",
                f"  - 链接：{citation.source_url}",
                f"  - 证据：{citation.evidence}",
            ]
        )
    lines.extend(
        [
            "",
            "---",
            "本讲解仅覆盖当前南越专题可信资料范围。",
        ]
    )
    return "\n".join(lines) + "\n"


def safe_download_name(entity_name: str, style: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", f"{entity_name}_{style}")
    return f"{value.strip('_') or '讲解稿'}.md"


def _neo4j_is_configured(settings: Settings) -> bool:
    return bool(
        settings.neo4j_uri
        and settings.neo4j_username
        and settings.neo4j_password
        and settings.neo4j_password.get_secret_value()
    )


def _ask_service(
    service: object,
    question: str,
    history: list[ConversationTurn] | None,
    answer_mode: AnswerMode,
    audience: Audience,
) -> AgentAnswer:
    """Keep test doubles and third-party service adapters using the legacy signature working."""
    if audience == Audience.ADULT and not history and answer_mode == AnswerMode.AUTO:
        return service.answer(question)
    kwargs: dict = {"history": history, "answer_mode": answer_mode}
    if audience == Audience.KIDS:
        kwargs["audience"] = audience
    return service.answer(question, **kwargs)
