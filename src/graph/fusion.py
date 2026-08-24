from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.extraction.models import Entity, ExtractionResult, Relation, RelationType
from src.preprocessing import load_corpus


class RelationKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1)
    relation: RelationType
    target_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)


class ResolutionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_id_map: dict[str, str] = Field(default_factory=dict)
    drop_entity_ids: list[str] = Field(default_factory=list)
    drop_relation_keys: list[RelationKey] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_disjoint_actions(self) -> "ResolutionConfig":
        overlap = set(self.canonical_id_map) & set(self.drop_entity_ids)
        if overlap:
            raise ValueError(
                "entity ids cannot be both mapped and dropped: " + ", ".join(sorted(overlap))
            )
        return self

    @classmethod
    def from_path(cls, path: str | Path) -> "ResolutionConfig":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


class FusionReport(BaseModel):
    input_documents: int
    input_entity_occurrences: int
    input_unique_entity_ids: int
    output_entities: int
    input_relations: int
    output_relations: int
    mapped_entity_ids: int
    dropped_entity_ids: int
    dropped_relations: int
    deduplicated_relations: int
    source_and_evidence_issues: list[dict[str, str]] = Field(default_factory=list)


def _resolve_id(entity_id: str, mappings: dict[str, str]) -> str:
    visited: list[str] = []
    current = entity_id
    while current in mappings:
        if current in visited:
            cycle = " -> ".join([*visited, current])
            raise ValueError(f"canonical id mapping contains a cycle: {cycle}")
        visited.append(current)
        current = mappings[current]
    return current


def _relation_key(relation: Relation) -> RelationKey:
    return RelationKey(
        source_id=relation.source_id,
        relation=relation.relation,
        target_id=relation.target_id,
        document_id=relation.document_id,
    )


def _validate_resolution(
    entities_by_id: dict[str, list[Entity]], config: ResolutionConfig
) -> dict[str, str]:
    known_ids = set(entities_by_id)
    unknown_sources = set(config.canonical_id_map) - known_ids
    unknown_drops = set(config.drop_entity_ids) - known_ids
    if unknown_sources:
        raise ValueError("mapping sources are missing: " + ", ".join(sorted(unknown_sources)))
    if unknown_drops:
        raise ValueError("drop entity ids are missing: " + ", ".join(sorted(unknown_drops)))

    resolved: dict[str, str] = {}
    for source_id in sorted(config.canonical_id_map):
        target_id = _resolve_id(source_id, config.canonical_id_map)
        if target_id not in known_ids:
            raise ValueError(f"canonical target is missing: {source_id} -> {target_id}")
        source_types = {entity.type for entity in entities_by_id[source_id]}
        target_types = {entity.type for entity in entities_by_id[target_id]}
        if len(source_types) != 1 or len(target_types) != 1 or source_types != target_types:
            raise ValueError(f"cross-type canonical mapping is not allowed: {source_id} -> {target_id}")
        resolved[source_id] = target_id
    return resolved


def _merge_entity(canonical_id: str, candidates: list[Entity]) -> Entity:
    canonical_candidates = [entity for entity in candidates if entity.id == canonical_id]
    if not canonical_candidates:
        raise ValueError(f"canonical entity has no source record: {canonical_id}")
    entity_types = {entity.type for entity in candidates}
    if len(entity_types) != 1:
        raise ValueError(f"cannot merge multiple entity types into {canonical_id}")

    name_source = max(
        canonical_candidates,
        key=lambda entity: (entity.confidence, len(entity.name), entity.name),
    )
    name = name_source.name
    aliases = {
        value
        for entity in candidates
        for value in [entity.name, *entity.aliases]
        if value and value != name
    }
    descriptions = [entity for entity in candidates if entity.description]
    description = ""
    if descriptions:
        description = max(
            descriptions,
            key=lambda entity: (
                entity.confidence,
                len(entity.description),
                entity.description,
            ),
        ).description

    return Entity(
        id=canonical_id,
        name=name,
        type=next(iter(entity_types)),
        aliases=sorted(aliases),
        description=description,
        source_ids=sorted({source for entity in candidates for source in entity.source_ids}),
        confidence=max(entity.confidence for entity in candidates),
    )


def fuse_extractions(
    input_dir: str | Path,
    resolution: ResolutionConfig | str | Path,
    *,
    raw_dir: str | Path = "data/raw",
) -> tuple[ExtractionResult, FusionReport]:
    input_root = Path(input_dir)
    if not input_root.is_dir():
        raise FileNotFoundError(f"extraction input directory does not exist: {input_root}")
    config = resolution if isinstance(resolution, ResolutionConfig) else ResolutionConfig.from_path(resolution)
    paths = sorted(input_root.glob("*.json"))
    if not paths:
        raise ValueError(f"no extraction JSON files found in {input_root}")

    results: list[ExtractionResult] = []
    entities_by_id: dict[str, list[Entity]] = defaultdict(list)
    for path in paths:
        result = ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))
        results.append(result)
        for entity in result.entities:
            entities_by_id[entity.id].append(entity)

    resolved_mappings = _validate_resolution(entities_by_id, config)
    drop_ids = set(config.drop_entity_ids)
    drop_relation_keys = set(config.drop_relation_keys)

    grouped_entities: dict[str, list[Entity]] = defaultdict(list)
    for result in results:
        for entity in result.entities:
            if entity.id in drop_ids:
                continue
            canonical_id = resolved_mappings.get(entity.id, entity.id)
            grouped_entities[canonical_id].append(entity)

    merged_entities = [
        _merge_entity(canonical_id, grouped_entities[canonical_id])
        for canonical_id in sorted(grouped_entities)
    ]

    grouped_relations: dict[tuple[str, str, str, str], list[Relation]] = defaultdict(list)
    dropped_relations = 0
    matched_drop_relation_keys: set[RelationKey] = set()
    for result in results:
        for relation in result.relations:
            if _relation_key(relation) in drop_relation_keys:
                matched_drop_relation_keys.add(_relation_key(relation))
                dropped_relations += 1
                continue
            if relation.source_id in drop_ids or relation.target_id in drop_ids:
                raise ValueError(
                    "a relation still references a dropped entity: "
                    f"{relation.source_id} -[{relation.relation.value}]-> {relation.target_id}"
                )
            source_id = resolved_mappings.get(relation.source_id, relation.source_id)
            target_id = resolved_mappings.get(relation.target_id, relation.target_id)
            rewritten = relation.model_copy(
                update={"source_id": source_id, "target_id": target_id}
            )
            key = (source_id, relation.relation.value, target_id, relation.document_id)
            grouped_relations[key].append(rewritten)

    unmatched_drop_keys = drop_relation_keys - matched_drop_relation_keys
    if unmatched_drop_keys:
        missing = sorted(
            f"{item.document_id}:{item.source_id}-[{item.relation.value}]->{item.target_id}"
            for item in unmatched_drop_keys
        )
        raise ValueError("configured drop relations are missing: " + ", ".join(missing))

    merged_relations: list[Relation] = []
    for key in sorted(grouped_relations):
        merged_relations.append(
            max(
                grouped_relations[key],
                key=lambda relation: (
                    relation.confidence,
                    len(relation.evidence),
                    relation.evidence,
                ),
            )
        )

    fused = ExtractionResult(entities=merged_entities, relations=merged_relations)
    documents = {document.doc_id: document for document in load_corpus(raw_dir)}
    issues: list[dict[str, str]] = []
    for entity in fused.entities:
        for source_id in entity.source_ids:
            if source_id not in documents:
                issues.append({"kind": "unknown_entity_source", "value": source_id})
    for relation in fused.relations:
        document = documents.get(relation.document_id)
        if document is None:
            issues.append({"kind": "unknown_relation_document", "value": relation.document_id})
        elif relation.evidence not in document.text:
            issues.append(
                {
                    "kind": "nonverbatim_evidence",
                    "value": f"{relation.document_id}: {relation.evidence}",
                }
            )
    if issues:
        raise ValueError("fused graph failed source/evidence audit: " + json.dumps(issues, ensure_ascii=False))

    input_relation_count = sum(len(result.relations) for result in results)
    report = FusionReport(
        input_documents=len(paths),
        input_entity_occurrences=sum(len(result.entities) for result in results),
        input_unique_entity_ids=len(entities_by_id),
        output_entities=len(fused.entities),
        input_relations=input_relation_count,
        output_relations=len(fused.relations),
        mapped_entity_ids=len(resolved_mappings),
        dropped_entity_ids=len(drop_ids),
        dropped_relations=dropped_relations,
        deduplicated_relations=input_relation_count - dropped_relations - len(fused.relations),
        source_and_evidence_issues=issues,
    )
    return fused, report


def write_graph_v1(
    result: ExtractionResult,
    report: FusionReport,
    output_path: str | Path,
    report_path: str | Path,
) -> None:
    graph_path = Path(output_path)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    fusion_report_path = Path(report_path)
    fusion_report_path.parent.mkdir(parents=True, exist_ok=True)
    fusion_report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
