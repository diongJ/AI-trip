from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from src.rag.models import GraphHit, RetrievalHit


class QuestionType(StrEnum):
    ENTITY_FACT = "entity_fact"
    RELATION_EXPLORATION = "relation_exploration"
    DESCRIPTION = "description"
    OUT_OF_SCOPE = "out_of_scope"


class ToolName(StrEnum):
    SEARCH_KG = "search_kg"
    SEARCH_DOCUMENTS = "search_documents"
    HYBRID_SEARCH = "hybrid_search"
    WEB_SEARCH = "web_search"
    NONE = "none"


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    WEB_SEARCH_ANSWERED = "web_search_answered"
    CLARIFICATION_NEEDED = "clarification_needed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    OUT_OF_SCOPE = "out_of_scope"
    REALTIME_UNAVAILABLE = "realtime_unavailable"
    SERVICE_UNAVAILABLE = "service_unavailable"


class AnswerMode(StrEnum):
    AUTO = "auto"
    BRIEF = "brief"
    DEEP = "deep"


class TemporalScope(StrEnum):
    CURRENT = "current"
    HISTORICAL = "historical"
    FUTURE = "future"


class VisitZone(StrEnum):
    WANGMU = "wangmu"
    CROSS_ZONE = "cross_zone"


class ClaimType(StrEnum):
    DIRECT_FACT = "direct_fact"
    SYNTHESIS = "synthesis"


class ConversationTurn(BaseModel):
    """A prior user/assistant exchange used only to resolve follow-up wording."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    question: str = Field(min_length=1)
    answer: str = ""


class RouteDecision(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    question_type: QuestionType
    tool: ToolName
    reason: str = Field(min_length=1)
    entity_query: str | None = None
    intent: str = "description"
    entities: list[str] = Field(default_factory=list)
    subqueries: list[str] = Field(default_factory=list)
    relations: list[str] = Field(default_factory=list)
    scope: Literal["in_scope", "out_of_scope"] = "in_scope"
    answer_mode: AnswerMode = AnswerMode.AUTO
    temporal_scope: TemporalScope = TemporalScope.CURRENT
    as_of: str | None = None
    visit_zone: VisitZone = VisitZone.WANGMU


class Citation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    doc_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: AnyHttpUrl
    evidence: str = Field(min_length=1)
    evidence_id: str = ""
    source_tier: Literal["core", "extended"] = "core"
    source_type: str = "official"
    evidence_role: Literal["factual", "curated_guidance"] = "factual"
    content_hash: str = ""
    retrieved_at: str = ""


class WebSource(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1)
    url: AnyHttpUrl
    accessed_at: str = Field(min_length=1)


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[RetrievalHit] = Field(default_factory=list)
    graph: list[GraphHit] = Field(default_factory=list)

    @property
    def has_evidence(self) -> bool:
        return bool(self.documents or self.graph)


class AnswerClaim(BaseModel):
    """One answer-level statement and the evidence used to support it."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(min_length=1)
    claim_type: ClaimType = ClaimType.DIRECT_FACT
    evidence_ids: list[str] = Field(min_length=1)


class AgentAnswer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    answer: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    web_sources: list[WebSource] = Field(default_factory=list)
    used_tools: list[ToolName] = Field(default_factory=list)
    route_reason: str = Field(min_length=1)
    insufficient_evidence: bool = False
    retrieved_documents: list[RetrievalHit] = Field(default_factory=list)
    graph_facts: list[GraphHit] = Field(default_factory=list)
    selected_evidence_ids: list[str] = Field(default_factory=list)
    claims: list[AnswerClaim] = Field(default_factory=list)
    claims_verified: bool = False
    source_tiers: list[str] = Field(default_factory=list)
    refusal_reason: str | None = None
    response_status: AnswerStatus = AnswerStatus.ANSWERED
    suggested_questions: list[str] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def require_citations_unless_insufficient(self) -> "AgentAnswer":
        if self.response_status == AnswerStatus.ANSWERED:
            if self.insufficient_evidence or not self.citations or self.web_sources:
                raise ValueError("grounded answers require local citations only")
        elif self.response_status == AnswerStatus.WEB_SEARCH_ANSWERED:
            if self.insufficient_evidence or self.citations or not self.web_sources:
                raise ValueError("web search answers require web sources and no local citations")
        else:
            if not self.insufficient_evidence:
                raise ValueError("non-answer response must be marked insufficient")
            if self.citations or self.web_sources:
                raise ValueError("insufficient responses cannot include sources")
        return self


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    answer: str = Field(min_length=1)
    selected_evidence_ids: list[str] = Field(default_factory=list)
    claims: list[AnswerClaim] = Field(default_factory=list)
    supported: bool = True
    refusal_reason: str | None = None


class WebSearchResult(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    answer: str = Field(min_length=1)
    sources: list[WebSource] = Field(min_length=1)
