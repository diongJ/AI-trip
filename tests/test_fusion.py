import json
from pathlib import Path
from hashlib import sha256

import pytest

from src.extraction.models import ExtractionResult
from src.graph.fusion import ResolutionConfig, fuse_extractions


def entity(
    entity_id: str,
    name: str,
    entity_type: str,
    doc_id: str,
    *,
    aliases: list[str] | None = None,
    description: str = "",
    confidence: float = 0.9,
) -> dict[str, object]:
    return {
        "id": entity_id,
        "name": name,
        "type": entity_type,
        "aliases": aliases or [],
        "description": description,
        "source_ids": [doc_id],
        "confidence": confidence,
    }


def relation(
    source_id: str,
    relation_type: str,
    target_id: str,
    doc_id: str,
    *,
    evidence: str = "赵眜葬于南越文王墓",
    confidence: float = 0.9,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "relation": relation_type,
        "target_id": target_id,
        "evidence": evidence,
        "document_id": doc_id,
        "confidence": confidence,
    }


def write_raw(
    root: Path,
    doc_id: str,
    text: str = "官方资料明确记载赵眜葬于南越文王墓，证据完整可核验。",
    *,
    evidence_role: str = "factual",
) -> None:
    payload = {
        "doc_id": doc_id,
        "title": "测试资料",
        "source_name": "测试来源" if evidence_role == "factual" else "AI-trip 项目整理",
        "source_url": "https://example.com/source",
        "source_type": "official" if evidence_role == "factual" else "other",
        "category": "tomb" if evidence_role == "factual" else "tourism",
        "retrieved_at": "2026-08-24",
        "text": text,
        "source_tier": "core" if evidence_role == "factual" else "extended",
        "evidence_role": evidence_role,
        "content_hash": sha256(text.encode("utf-8")).hexdigest(),
        "review_status": "approved",
    }
    (root / f"{doc_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def write_result(root: Path, doc_id: str, payload: dict[str, object]) -> None:
    result = ExtractionResult.model_validate(payload)
    (root / f"{doc_id}.json").write_text(result.model_dump_json(), encoding="utf-8")


def test_fusion_rewrites_endpoints_and_merges_attributes(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    raw = tmp_path / "raw"
    graph.mkdir()
    raw.mkdir()
    write_raw(raw, "DOC_001")
    write_raw(raw, "DOC_002")
    write_result(
        graph,
        "DOC_001",
        {
            "entities": [
                entity("person:南越文帝", "南越文帝", "Person", "DOC_001", aliases=["文帝"]),
                entity("tomb:南越文王墓", "南越文王墓", "Tomb", "DOC_001"),
            ],
            "relations": [relation("person:南越文帝", "BURIED_IN", "tomb:南越文王墓", "DOC_001")],
        },
    )
    write_result(
        graph,
        "DOC_002",
        {
            "entities": [
                entity("person:赵眜", "赵眜", "Person", "DOC_002", description="南越国第二代王", confidence=1.0),
                entity("tomb:南越文王墓", "南越文王墓", "Tomb", "DOC_002"),
            ],
            "relations": [relation("person:赵眜", "BURIED_IN", "tomb:南越文王墓", "DOC_002")],
        },
    )
    config = ResolutionConfig(canonical_id_map={"person:南越文帝": "person:赵眜"})

    fused, report = fuse_extractions(graph, config, raw_dir=raw)

    person = next(item for item in fused.entities if item.id == "person:赵眜")
    assert person.aliases == ["南越文帝", "文帝"]
    assert person.source_ids == ["DOC_001", "DOC_002"]
    assert person.description == "南越国第二代王"
    assert fused.relations[0].source_id == "person:赵眜"
    assert report.input_unique_entity_ids == 3
    assert report.output_entities == 2


def test_fusion_resolves_mapping_chains(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    raw = tmp_path / "raw"
    graph.mkdir()
    raw.mkdir()
    write_raw(raw, "DOC_001")
    write_result(
        graph,
        "DOC_001",
        {
            "entities": [
                entity("person:a", "甲", "Person", "DOC_001"),
                entity("person:b", "乙", "Person", "DOC_001"),
                entity("person:c", "丙", "Person", "DOC_001"),
            ],
            "relations": [],
        },
    )
    config = ResolutionConfig(canonical_id_map={"person:a": "person:b", "person:b": "person:c"})

    fused, _ = fuse_extractions(graph, config, raw_dir=raw)

    assert [item.id for item in fused.entities] == ["person:c"]
    assert fused.entities[0].aliases == ["乙", "甲"]


def test_fusion_rejects_mapping_cycle(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    raw = tmp_path / "raw"
    graph.mkdir()
    raw.mkdir()
    write_raw(raw, "DOC_001")
    write_result(
        graph,
        "DOC_001",
        {"entities": [entity("person:a", "甲", "Person", "DOC_001"), entity("person:b", "乙", "Person", "DOC_001")], "relations": []},
    )
    config = ResolutionConfig(canonical_id_map={"person:a": "person:b", "person:b": "person:a"})

    with pytest.raises(ValueError, match="cycle"):
        fuse_extractions(graph, config, raw_dir=raw)


def test_fusion_rejects_cross_type_mapping(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    raw = tmp_path / "raw"
    graph.mkdir()
    raw.mkdir()
    write_raw(raw, "DOC_001")
    write_result(
        graph,
        "DOC_001",
        {"entities": [entity("person:a", "甲", "Person", "DOC_001"), entity("tomb:b", "乙墓", "Tomb", "DOC_001")], "relations": []},
    )
    config = ResolutionConfig(canonical_id_map={"person:a": "tomb:b"})

    with pytest.raises(ValueError, match="cross-type"):
        fuse_extractions(graph, config, raw_dir=raw)


def test_fusion_drops_curated_entities_and_relations(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    raw = tmp_path / "raw"
    graph.mkdir()
    raw.mkdir()
    write_raw(raw, "DOC_001")
    write_result(
        graph,
        "DOC_001",
        {
            "entities": [
                entity("person:赵眜", "赵眜", "Person", "DOC_001"),
                entity("tomb:南越文王墓", "南越文王墓", "Tomb", "DOC_001"),
                entity("exhibition:章节", "章节", "Exhibition", "DOC_001"),
            ],
            "relations": [relation("person:赵眜", "BURIED_IN", "tomb:南越文王墓", "DOC_001")],
        },
    )
    config = ResolutionConfig.model_validate(
        {
            "drop_entity_ids": ["exhibition:章节"],
            "drop_relation_keys": [
                {
                    "source_id": "person:赵眜",
                    "relation": "BURIED_IN",
                    "target_id": "tomb:南越文王墓",
                    "document_id": "DOC_001",
                }
            ],
        }
    )

    fused, report = fuse_extractions(graph, config, raw_dir=raw)

    assert len(fused.entities) == 2
    assert fused.relations == []
    assert report.dropped_entity_ids == 1
    assert report.dropped_relations == 1


def test_fusion_rejects_curated_guidance_as_graph_source(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    raw = tmp_path / "raw"
    graph.mkdir()
    raw.mkdir()
    write_raw(raw, "DOC_001", evidence_role="curated_guidance")
    write_result(
        graph,
        "DOC_001",
        {
            "entities": [entity("exhibition:建议路线", "建议路线", "Exhibition", "DOC_001")],
            "relations": [],
        },
    )

    with pytest.raises(ValueError, match="curated_entity_source"):
        fuse_extractions(graph, ResolutionConfig(), raw_dir=raw)


def test_fusion_rejects_relation_left_on_dropped_entity(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    raw = tmp_path / "raw"
    graph.mkdir()
    raw.mkdir()
    write_raw(raw, "DOC_001")
    write_result(
        graph,
        "DOC_001",
        {
            "entities": [
                entity("person:赵眜", "赵眜", "Person", "DOC_001"),
                entity("tomb:南越文王墓", "南越文王墓", "Tomb", "DOC_001"),
            ],
            "relations": [relation("person:赵眜", "BURIED_IN", "tomb:南越文王墓", "DOC_001")],
        },
    )

    with pytest.raises(ValueError, match="still references"):
        fuse_extractions(
            graph,
            ResolutionConfig(drop_entity_ids=["person:赵眜"]),
            raw_dir=raw,
        )


def test_fusion_deduplicates_relations_deterministically(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    raw = tmp_path / "raw"
    graph.mkdir()
    raw.mkdir()
    write_raw(raw, "DOC_001", "这是一段足够长的官方测试原文，包含短证据；赵眜葬于南越文王墓。")
    write_result(
        graph,
        "DOC_001",
        {
            "entities": [
                entity("person:赵眜", "赵眜", "Person", "DOC_001"),
                entity("tomb:南越文王墓", "南越文王墓", "Tomb", "DOC_001"),
            ],
            "relations": [
                relation("person:赵眜", "BURIED_IN", "tomb:南越文王墓", "DOC_001", evidence="短证据", confidence=0.8),
                relation("person:赵眜", "BURIED_IN", "tomb:南越文王墓", "DOC_001", confidence=0.9),
            ],
        },
    )

    fused, report = fuse_extractions(graph, ResolutionConfig(), raw_dir=raw)

    assert len(fused.relations) == 1
    assert fused.relations[0].evidence == "赵眜葬于南越文王墓"
    assert report.deduplicated_relations == 1
