import pytest
from pydantic import ValidationError

from src.extraction.models import Entity, ExtractionResult, Relation


def entity(entity_id: str, name: str, entity_type: str) -> dict[str, object]:
    return {
        "id": entity_id,
        "name": name,
        "type": entity_type,
        "aliases": [],
        "description": "",
        "source_ids": ["DOC_001"],
        "confidence": 0.9,
    }


def relation(source_id: str, relation_type: str, target_id: str) -> dict[str, object]:
    return {
        "source_id": source_id,
        "relation": relation_type,
        "target_id": target_id,
        "evidence": "原文证据",
        "document_id": "DOC_001",
        "confidence": 0.9,
    }


def test_valid_extraction_accepts_schema_direction() -> None:
    result = ExtractionResult.model_validate(
        {
            "entities": [
                entity("person:赵眜", "赵眜", "Person"),
                entity("tomb:南越文王墓", "南越文王墓", "Tomb"),
            ],
            "relations": [
                relation("person:赵眜", "BURIED_IN", "tomb:南越文王墓")
            ],
        }
    )
    assert len(result.entities) == 2
    assert len(result.relations) == 1


@pytest.mark.parametrize(
    ("payload", "error_fragment"),
    [
        ({**entity("x", "名称", "Unknown")}, "type"),
        ({**entity("x", "名称", "Person"), "confidence": 1.1}, "confidence"),
        ({**entity("x", "", "Person")}, "name"),
        ({**entity("x", "名称", "Person"), "source_ids": []}, "source_ids"),
    ],
)
def test_entity_rejects_invalid_fields(payload: dict[str, object], error_fragment: str) -> None:
    with pytest.raises(ValidationError, match=error_fragment):
        Entity.model_validate(payload)


def test_relation_rejects_empty_evidence() -> None:
    payload = relation("a", "BURIED_IN", "b")
    payload["evidence"] = ""
    with pytest.raises(ValidationError, match="evidence"):
        Relation.model_validate(payload)


def test_extraction_rejects_missing_entity_reference() -> None:
    with pytest.raises(ValidationError, match="missing from this extraction"):
        ExtractionResult.model_validate(
            {
                "entities": [entity("person:赵眜", "赵眜", "Person")],
                "relations": [
                    relation("person:赵眜", "BURIED_IN", "tomb:南越文王墓")
                ],
            }
        )


def test_extraction_rejects_reversed_relation_direction() -> None:
    with pytest.raises(ValidationError, match="invalid direction"):
        ExtractionResult.model_validate(
            {
                "entities": [
                    entity("person:赵眜", "赵眜", "Person"),
                    entity("tomb:南越文王墓", "南越文王墓", "Tomb"),
                ],
                "relations": [
                    relation("tomb:南越文王墓", "BURIED_IN", "person:赵眜")
                ],
            }
        )


def test_aliases_are_trimmed_deduplicated_and_exclude_name() -> None:
    payload = entity("person:赵眜", "赵眜", "Person")
    payload["aliases"] = [" 南越文王 ", "南越文王", "赵眜", ""]
    parsed = Entity.model_validate(payload)
    assert parsed.aliases == ["南越文王"]

