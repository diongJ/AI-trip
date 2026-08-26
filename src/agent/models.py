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
    NONE = "none"


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    CLARIFICATION_NEEDED = "clarification_needed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    OUT_OF_SCOPE = "out_of_scope"
    REALTIME_UNAVAILABLE = "realtime_unavailable"
    SERVICE_UNAVAILABLE = "service_unavailable"


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


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[RetrievalHit] = Field(default_factory=list)
    graph: list[GraphHit] = Field(default_factory=list)

    @property
    def has_evidence(self) -> bool:
        return bool(self.documents or self.graph)


class AgentAnswer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    answer: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    used_tools: list[ToolName] = Field(default_factory=list)
    route_reason: str = Field(min_length=1)
    insufficient_evidence: bool = False
    retrieved_documents: list[RetrievalHit] = Field(default_factory=list)
    graph_facts: list[GraphHit] = Field(default_factory=list)
    selected_evidence_ids: list[str] = Field(default_factory=list)
    source_tiers: list[str] = Field(default_factory=list)
    refusal_reason: str | None = None
    response_status: AnswerStatus = AnswerStatus.ANSWERED
    suggested_questions: list[str] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def require_citations_unless_insufficient(self) -> "AgentAnswer":
        if self.response_status == AnswerStatus.ANSWERED and self.insufficient_evidence:
            raise ValueError("answered response cannot be marked insufficient")
        if self.response_status != AnswerStatus.ANSWERED and not self.insufficient_evidence:
            raise ValueError("non-answer response must be marked insufficient")
        if not self.insufficient_evidence and not self.citations:
            raise ValueError("answers with sufficient evidence must include citations")
        if self.insufficient_evidence and self.citations:
            raise ValueError("insufficient responses cannot include citations")
        return self


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    answer: str = Field(min_length=1)
    selected_evidence_ids: list[str] = Field(default_factory=list)
    supported: bool = True
    refusal_reason: str | None = None
