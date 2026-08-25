from __future__ import annotations

from enum import StrEnum

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


class RouteDecision(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    question_type: QuestionType
    tool: ToolName
    reason: str = Field(min_length=1)
    entity_query: str | None = None


class Citation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    doc_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: AnyHttpUrl
    evidence: str = Field(min_length=1)


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

    @model_validator(mode="after")
    def require_citations_unless_insufficient(self) -> "AgentAnswer":
        if not self.insufficient_evidence and not self.citations:
            raise ValueError("answers with sufficient evidence must include citations")
        return self
