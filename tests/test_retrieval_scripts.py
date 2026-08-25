import json
import sys
from pathlib import Path

from scripts.build_graph_v1 import build_graph_v1
from src.extraction.models import Entity, ExtractionResult


def test_graph_builder_does_not_parse_parent_cli_arguments(
    tmp_path: Path, monkeypatch
) -> None:
    input_dir = tmp_path / "by_document"
    raw_dir = tmp_path / "raw"
    input_dir.mkdir()
    raw_dir.mkdir()
    result = ExtractionResult(
        entities=[
            Entity(
                id="person:赵眜",
                name="赵眜",
                type="Person",
                source_ids=["DOC_001"],
                confidence=1.0,
            )
        ]
    )
    (input_dir / "DOC_001.json").write_text(
        result.model_dump_json(), encoding="utf-8"
    )
    (raw_dir / "DOC_001.json").write_text(
        json.dumps(
            {
                "doc_id": "DOC_001",
                "title": "赵眜",
                "source_name": "测试来源",
                "source_url": "https://example.com/source",
                "source_type": "official",
                "category": "person",
                "retrieved_at": "2026-08-25",
                "text": "这是一段长度足够的测试资料，介绍南越国第二代王赵眜。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    resolution = tmp_path / "resolution.json"
    resolution.write_text(
        json.dumps(
            {
                "canonical_id_map": {},
                "drop_entity_ids": [],
                "drop_relation_keys": [],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "knowledge_graph_v1.json"
    report = tmp_path / "fusion_report.json"
    monkeypatch.setattr(sys, "argv", ["ask.py", "文帝行玺是什么材料？", "--llm"])

    summary = build_graph_v1(
        input_dir=input_dir,
        raw_dir=raw_dir,
        resolution=resolution,
        output=output,
        report_path=report,
    )

    assert summary["output_entities"] == 1
    assert output.exists()
    assert report.exists()
