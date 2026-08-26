from __future__ import annotations

from typing import Any

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


class DocumentChunk(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: AnyHttpUrl
    category: str = Field(min_length=1)
    source_tier: str = "core"
    topic_tags: list[str] = Field(default_factory=list)
    retrieved_at: str = ""
    published_at: str | None = None
    content_hash: str = ""


class RetrievalHit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    content: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    rank: int = Field(ge=1)
    backend: str = Field(min_length=1)
    metadata: dict[str, Any]

    @model_validator(mode="after")
    def require_source_metadata(self) -> "RetrievalHit":
        required = {
            "doc_id", "title", "source_name", "source_url", "category", "chunk_id",
            "source_tier", "retrieved_at", "fusion_score",
        }
        missing = sorted(required.difference(self.metadata))
        if missing:
            raise ValueError(f"retrieval metadata missing required fields: {missing}")
        return self


class GraphEntity(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)


class GraphHit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_entity: GraphEntity
    relation: str = Field(min_length=1)
    target_entity: GraphEntity
    direction: str = Field(pattern=r"^(outgoing|incoming)$")
    document_id: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    backend: str = Field(min_length=1)
