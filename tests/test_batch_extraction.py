import json
from pathlib import Path

import pytest

from src.extraction.batch import BatchExtractionRunner
from src.extraction.deepseek import DeepSeekError
from src.extraction.models import ExtractionResult


def document(doc_id: str) -> dict[str, object]:
    return {
        "doc_id": doc_id,
        "title": f"资料 {doc_id}",
        "source_name": "南越王博物院",
        "source_url": "https://www.nywmuseum.org.cn/",
        "source_type": "official",
        "category": "tomb",
        "retrieved_at": "2026-08-24",
        "text": "南越文王墓是南越国第二代王赵眜的墓葬，用于批量抽取测试。",
    }


def extraction(doc_id: str) -> ExtractionResult:
    return ExtractionResult.model_validate(
        {
            "entities": [
                {
                    "id": "person:赵眜",
                    "name": "赵眜",
                    "type": "Person",
                    "aliases": [],
                    "description": "",
                    "source_ids": [doc_id],
                    "confidence": 0.9,
                },
                {
                    "id": "tomb:南越文王墓",
                    "name": "南越文王墓",
                    "type": "Tomb",
                    "aliases": [],
                    "description": "",
                    "source_ids": [doc_id],
                    "confidence": 0.9,
                },
            ],
            "relations": [
                {
                    "source_id": "person:赵眜",
                    "relation": "BURIED_IN",
                    "target_id": "tomb:南越文王墓",
                    "evidence": "南越文王墓是南越国第二代王赵眜的墓葬",
                    "document_id": doc_id,
                    "confidence": 0.9,
                }
            ],
        }
    )


class FakeExtractor:
    def __init__(self, failures: dict[str, list[DeepSeekError]] | None = None) -> None:
        self.failures = failures or {}
        self.calls: list[str] = []

    def extract(self, _: str, document_id: str) -> ExtractionResult:
        self.calls.append(document_id)
        queued = self.failures.get(document_id, [])
        if queued:
            raise queued.pop(0)
        return extraction(document_id)


def write_document(root: Path, doc_id: str, *, filename: str | None = None) -> Path:
    path = root / (filename or f"{doc_id}.json")
    path.write_text(json.dumps(document(doc_id), ensure_ascii=False), encoding="utf-8")
    return path


def test_batch_writes_reloadable_result_and_summary(tmp_path: Path) -> None:
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "graph"
    input_dir.mkdir()
    write_document(input_dir, "DOC_001")

    report = BatchExtractionRunner(FakeExtractor()).run(input_dir, output_dir)

    stored = ExtractionResult.model_validate_json(
        (output_dir / "DOC_001.json").read_text(encoding="utf-8")
    )
    assert len(stored.entities) == 2
    summary = report.to_dict()
    assert summary["total"] == 1
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    assert summary["skipped"] == 0
    assert summary["entities"] == 2
    assert summary["relations"] == 1


def test_batch_continues_after_invalid_input_and_extraction_error(tmp_path: Path) -> None:
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "graph"
    input_dir.mkdir()
    (input_dir / "bad.json").write_text("not json", encoding="utf-8")
    write_document(input_dir, "DOC_001")
    write_document(input_dir, "DOC_002")
    extractor = FakeExtractor(
        {"DOC_001": [DeepSeekError("invalid schema", retryable=False)]}
    )

    report = BatchExtractionRunner(extractor).run(input_dir, output_dir)

    assert report.to_dict()["failed"] == 2
    assert report.to_dict()["succeeded"] == 1
    assert (output_dir / "DOC_002.json").exists()


def test_batch_skips_valid_existing_output_unless_forced(tmp_path: Path) -> None:
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "graph"
    input_dir.mkdir()
    output_dir.mkdir()
    write_document(input_dir, "DOC_001")
    (output_dir / "DOC_001.json").write_text(
        extraction("DOC_001").model_dump_json(), encoding="utf-8"
    )
    extractor = FakeExtractor()

    skipped = BatchExtractionRunner(extractor).run(input_dir, output_dir)
    forced = BatchExtractionRunner(extractor).run(input_dir, output_dir, force=True)

    assert skipped.to_dict()["skipped"] == 1
    assert forced.to_dict()["succeeded"] == 1
    assert extractor.calls == ["DOC_001"]


def test_batch_retries_only_retryable_errors(tmp_path: Path) -> None:
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "graph"
    input_dir.mkdir()
    write_document(input_dir, "DOC_001")
    extractor = FakeExtractor(
        {"DOC_001": [DeepSeekError("timeout", retryable=True)]}
    )

    report = BatchExtractionRunner(
        extractor, max_attempts=3, retry_delay_seconds=0
    ).run(input_dir, output_dir)

    assert report.to_dict()["succeeded"] == 1
    assert extractor.calls == ["DOC_001", "DOC_001"]
    assert report.items[0].attempts == 2


def test_batch_rejects_duplicate_doc_ids(tmp_path: Path) -> None:
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "graph"
    input_dir.mkdir()
    write_document(input_dir, "DOC_001", filename="a.json")
    write_document(input_dir, "DOC_001", filename="b.json")

    report = BatchExtractionRunner(FakeExtractor()).run(input_dir, output_dir)

    assert report.to_dict()["succeeded"] == 1
    assert report.to_dict()["failed"] == 1
    assert report.items[1].error == "duplicate doc_id DOC_001"


def test_batch_drops_relation_with_nonverbatim_evidence(tmp_path: Path) -> None:
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "graph"
    input_dir.mkdir()
    write_document(input_dir, "DOC_001")
    invalid_evidence = extraction("DOC_001")
    invalid_evidence.relations[0].evidence = "原文中不存在的改写证据"

    class EvidenceExtractor:
        def extract(self, _: str, __: str) -> ExtractionResult:
            return invalid_evidence

    report = BatchExtractionRunner(EvidenceExtractor()).run(input_dir, output_dir)
    stored = ExtractionResult.model_validate_json(
        (output_dir / "DOC_001.json").read_text(encoding="utf-8")
    )

    assert stored.relations == []
    assert report.to_dict()["dropped_relations"] == 1


def test_batch_sanitizes_ungrounded_description_alias_and_relation(tmp_path: Path) -> None:
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "graph"
    input_dir.mkdir()
    write_document(input_dir, "DOC_001")
    result = extraction("DOC_001")
    result.entities[0].description = "原文没有提供的常识"
    result.entities[0].aliases = ["未在原文出现的别名"]
    result.relations[0].evidence = "南越文王墓"

    class UngroundedExtractor:
        def extract(self, _: str, __: str) -> ExtractionResult:
            return result

    report = BatchExtractionRunner(UngroundedExtractor()).run(input_dir, output_dir)
    stored = ExtractionResult.model_validate_json(
        (output_dir / "DOC_001.json").read_text(encoding="utf-8")
    )

    assert stored.entities[0].description == ""
    assert stored.entities[0].aliases == []
    assert stored.relations == []
    assert report.to_dict()["cleared_descriptions"] == 1
    assert report.to_dict()["dropped_aliases"] == 1


def test_batch_rejects_missing_input_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="input directory"):
        BatchExtractionRunner(FakeExtractor()).run(
            tmp_path / "missing", tmp_path / "graph"
        )
