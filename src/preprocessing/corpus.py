from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

DOC_ID_RE = re.compile(r"^DOC_\d{3}$")


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

    @field_validator("doc_id")
    @classmethod
    def validate_doc_id(cls, value: str) -> str:
        if not DOC_ID_RE.fullmatch(value):
            raise ValueError("doc_id must match DOC_001 format")
        return value


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
        documents.append(document)

    if errors:
        raise CorpusValidationError("\n".join(errors))
    return documents
