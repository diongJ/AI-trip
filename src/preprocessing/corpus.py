from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

DOC_ID_RE = re.compile(r"^DOC_\d{3}$")
EvidenceRole = Literal["factual", "curated_guidance"]
TemporalScope = Literal["all", "current", "historical", "future"]


class CorpusValidationError(ValueError):
    """Raised when one or more raw corpus files fail validation."""


class CorpusDocument(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    doc_id: str
    title: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: AnyHttpUrl
    source_type: str = Field(pattern=r"^(official|academic|media|museum|book|other)$")
    category: str = Field(
        pattern=r"^(museum|tomb|person|relic|history|culture|exhibition|tourism)$"
    )
    retrieved_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    text: str = Field(min_length=20)
    source_tier: Literal["core", "extended"] = "core"
    evidence_role: EvidenceRole
    topic_tags: list[str] = Field(default_factory=list)
    published_at: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_status: Literal["approved", "sample_review", "pending", "rejected"]
    version: int = Field(default=1, ge=1)
    effective_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    effective_until: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    last_checked_at: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    volatility: str = "stable"
    zone: str | None = None
    floor: str | None = None
    visitor_types: list[str] = Field(default_factory=list)
    recommended_duration: int | None = Field(default=None, ge=1)

    @field_validator("doc_id")
    @classmethod
    def validate_doc_id(cls, value: str) -> str:
        if not DOC_ID_RE.fullmatch(value):
            raise ValueError("doc_id must match DOC_001 format")
        return value

    @field_validator("topic_tags")
    @classmethod
    def clean_topic_tags(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    @model_validator(mode="after")
    def validate_trust_metadata(self) -> "CorpusDocument":
        expected = sha256(self.text.encode("utf-8")).hexdigest()
        if self.content_hash != expected:
            raise ValueError("content_hash does not match text")
        if self.source_tier == "core" and self.review_status != "approved":
            raise ValueError("core documents must be approved")
        if self.source_tier == "core" and self.evidence_role != "factual":
            raise ValueError("core documents must be factual")
        if self.evidence_role == "curated_guidance" and (
            self.category != "tourism" or self.source_type != "other"
        ):
            raise ValueError("curated guidance must use tourism category and other source_type")
        return self


def load_corpus(root: str | Path = "data/raw") -> list[CorpusDocument]:
    root_path = Path(root)
    documents: list[CorpusDocument] = []
    errors: list[str] = []
    seen_ids: set[str] = set()

    for path in sorted(root_path.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            document = CorpusDocument.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - collect all file errors for review
            errors.append(f"{path}: {exc}")
            continue

        if document.doc_id in seen_ids:
            errors.append(f"{path}: duplicate doc_id {document.doc_id}")
            continue
        seen_ids.add(document.doc_id)
        if document.review_status not in {"approved", "sample_review"}:
            continue
        documents.append(document)

    if errors:
        raise CorpusValidationError("\n".join(errors))
    return documents
