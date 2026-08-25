import json
from pathlib import Path

from src.extraction.audit import audit_extractions

from test_batch_extraction import document, extraction


def test_audit_reports_counts_and_valid_provenance(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    graph = tmp_path / "graph"
    raw.mkdir()
    graph.mkdir()
    (raw / "DOC_001.json").write_text(
        json.dumps(document("DOC_001"), ensure_ascii=False), encoding="utf-8"
    )
    (graph / "DOC_001.json").write_text(
        extraction("DOC_001").model_dump_json(), encoding="utf-8"
    )

    report = audit_extractions(raw, graph)

    assert report["documents"] == 1
    assert report["unique_entity_ids"] == 2
    assert report["relations"] == 1
    assert report["issues"] == []


def test_audit_finds_missing_output_and_nonverbatim_evidence(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    graph = tmp_path / "graph"
    raw.mkdir()
    graph.mkdir()
    for doc_id in ("DOC_001", "DOC_002"):
        (raw / f"{doc_id}.json").write_text(
            json.dumps(document(doc_id), ensure_ascii=False), encoding="utf-8"
        )
    result = extraction("DOC_001")
    result.relations[0].evidence = "模型改写的证据"
    (graph / "DOC_001.json").write_text(
        result.model_dump_json(), encoding="utf-8"
    )

    report = audit_extractions(raw, graph)

    assert report["missing_outputs"] == ["DOC_002.json"]
    assert report["issues"][0]["kind"] == "nonverbatim_evidence"
