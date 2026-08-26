from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.extraction.models import ExtractionResult
from src.preprocessing import load_corpus


def audit_extractions(
    raw_dir: str | Path = "data/raw",
    graph_dir: str | Path = "data/graph/by_document",
    *,
    source_tier: str | None = None,
) -> dict[str, object]:
    documents = {
        document.doc_id: document
        for document in load_corpus(raw_dir)
        if source_tier is None or document.source_tier == source_tier
    }
    graph_root = Path(graph_dir)
    expected_files = {f"{doc_id}.json" for doc_id in documents}
    actual_files = {path.name for path in graph_root.glob("*.json")}
    entity_types: Counter[str] = Counter()
    relation_types: Counter[str] = Counter()
    unique_entity_ids: set[str] = set()
    issues: list[dict[str, str]] = []

    for doc_id, document in sorted(documents.items()):
        path = graph_root / f"{doc_id}.json"
        if not path.exists():
            continue
        result = ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))
        for entity in result.entities:
            unique_entity_ids.add(entity.id)
            entity_types[entity.type.value] += 1
            if doc_id not in entity.source_ids:
                issues.append(
                    {"doc_id": doc_id, "kind": "entity_source", "value": entity.id}
                )
        for relation in result.relations:
            relation_types[relation.relation.value] += 1
            if relation.document_id != doc_id:
                issues.append(
                    {
                        "doc_id": doc_id,
                        "kind": "relation_document",
                        "value": relation.document_id,
                    }
                )
            if relation.evidence not in document.text:
                issues.append(
                    {
                        "doc_id": doc_id,
                        "kind": "nonverbatim_evidence",
                        "value": relation.evidence,
                    }
                )

    return {
        "documents": len(documents),
        "outputs": len(actual_files),
        "missing_outputs": sorted(expected_files - actual_files),
        "unexpected_outputs": sorted(actual_files - expected_files),
        "entity_occurrences": sum(entity_types.values()),
        "unique_entity_ids": len(unique_entity_ids),
        "entity_types": dict(sorted(entity_types.items())),
        "relations": sum(relation_types.values()),
        "relation_types": dict(sorted(relation_types.items())),
        "issues": issues,
    }
