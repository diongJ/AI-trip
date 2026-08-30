"""Validated, versioned evidence paths for the public museum experience."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS_FILE = ROOT / "data" / "curated" / "exploration_paths_v1.json"
DEFAULT_GRAPH_FILE = ROOT / "data" / "graph" / "knowledge_graph_v1.json"
RELATION_LABELS = {
    "BELONGS_TO_CATEGORY": "属于类别",
    "BELONGS_TO_STATE": "属于",
    "BURIED_IN": "葬于",
    "CREATED_IN": "创制于",
    "EXCAVATED_FROM": "出土于",
    "HAS_PATTERN": "饰有",
    "INVOLVES_PERSON": "涉及",
    "MADE_OF": "由……制成",
    "OCCURRED_IN": "发生于",
    "REFLECTS_CULTURE": "反映",
    "RELATED_TO_PERSON": "证实关联",
}


class ExplorationStep(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    conclusion: str = Field(min_length=1)
    bridge: str = Field(min_length=1)
    source_entity: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    target_entity: str = Field(min_length=1)
    document_id: str = Field(pattern=r"^DOC_\d+$")
    evidence: str = Field(min_length=1)
    ask_prompt: str = Field(min_length=1)


class ExplorationPath(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    intro: str = Field(min_length=1)
    conclusion: str = Field(min_length=1)
    steps: list[ExplorationStep] = Field(min_length=2)


class ExplorationCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    paths: list[ExplorationPath] = Field(min_length=1)


class ExplorationDataError(ValueError):
    """Raised when a curated path no longer matches reviewed source data."""


def relation_label(relation: str) -> str:
    return RELATION_LABELS.get(relation, relation)


def _load_documents(raw_dir: Path) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for path in raw_dir.rglob("DOC_*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        doc_id = str(payload.get("doc_id", ""))
        if doc_id:
            documents[doc_id] = payload
    return documents


@lru_cache(maxsize=1)
def load_exploration_paths(
    paths_file: Path = DEFAULT_PATHS_FILE,
    graph_file: Path = DEFAULT_GRAPH_FILE,
    raw_dir: Path = ROOT / "data" / "raw",
) -> dict[str, Any]:
    """Load paths and fail fast when any claim loses its graph/source grounding."""
    collection = ExplorationCollection.model_validate_json(paths_file.read_text(encoding="utf-8"))
    graph = json.loads(graph_file.read_text(encoding="utf-8"))
    entity_names = {entity["id"]: entity["name"] for entity in graph["entities"]}
    relations = {
        (
            entity_names[row["source_id"]],
            row["relation"],
            entity_names[row["target_id"]],
            row["document_id"],
            row["evidence"],
        )
        for row in graph["relations"]
    }
    documents = _load_documents(raw_dir)
    enriched_paths: list[dict[str, Any]] = []
    seen_path_ids: set[str] = set()
    for path in collection.paths:
        if path.id in seen_path_ids:
            raise ExplorationDataError(f"duplicate exploration path id: {path.id}")
        seen_path_ids.add(path.id)
        path_payload = path.model_dump()
        enriched_steps = []
        seen_step_ids: set[str] = set()
        for step in path.steps:
            if step.id in seen_step_ids:
                raise ExplorationDataError(f"duplicate step id in {path.id}: {step.id}")
            seen_step_ids.add(step.id)
            relation_key = (
                step.source_entity,
                step.relation,
                step.target_entity,
                step.document_id,
                step.evidence,
            )
            if relation_key not in relations:
                raise ExplorationDataError(f"path step does not match graph evidence: {path.id}/{step.id}")
            document = documents.get(step.document_id)
            if document is None:
                raise ExplorationDataError(f"unknown path document: {step.document_id}")
            if document.get("review_status") != "approved" or document.get("evidence_role") != "factual":
                raise ExplorationDataError(f"path document is not approved factual evidence: {step.document_id}")
            if step.evidence not in str(document.get("text", "")):
                raise ExplorationDataError(f"path evidence is absent from document: {path.id}/{step.id}")
            enriched_steps.append(
                {
                    **step.model_dump(),
                    "relation_label": relation_label(step.relation),
                    "citation": {
                        "doc_id": step.document_id,
                        "title": document["title"],
                        "source_name": document["source_name"],
                        "source_url": document["source_url"],
                        "evidence": step.evidence,
                    },
                }
            )
        path_payload["steps"] = enriched_steps
        enriched_paths.append(path_payload)
    return {"version": collection.version, "paths": enriched_paths}
