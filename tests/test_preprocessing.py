import json
from hashlib import sha256

import pytest

from src.preprocessing import CorpusDocument, CorpusValidationError, load_corpus


def valid_document() -> dict[str, object]:
    text = "南越文王墓是南越王博物院王墓展区的核心研究对象，用于测试语料校验。"
    return {
        "doc_id": "DOC_001",
        "title": "南越文王墓",
        "source_name": "南越王博物院",
        "source_url": "https://www.nywmuseum.org.cn/",
        "source_type": "official",
        "category": "tomb",
        "retrieved_at": "2026-08-23",
        "text": text,
        "evidence_role": "factual",
        "content_hash": sha256(text.encode("utf-8")).hexdigest(),
        "review_status": "approved",
    }


def test_corpus_document_accepts_day2_fields() -> None:
    parsed = CorpusDocument.model_validate(valid_document())
    assert parsed.doc_id == "DOC_001"
    assert parsed.source_name == "南越王博物院"


def test_corpus_document_rejects_nonstandard_doc_id() -> None:
    payload = valid_document()
    payload["doc_id"] = "relic1"

    with pytest.raises(ValueError, match="DOC_001"):
        CorpusDocument.model_validate(payload)


def test_load_corpus_rejects_duplicate_doc_ids(tmp_path) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text(json.dumps(valid_document(), ensure_ascii=False), encoding="utf-8")
    second.write_text(json.dumps(valid_document(), ensure_ascii=False), encoding="utf-8")

    with pytest.raises(CorpusValidationError, match="duplicate doc_id"):
        load_corpus(tmp_path)


@pytest.mark.parametrize("field", ["evidence_role", "content_hash", "review_status"])
def test_trust_metadata_must_be_persisted(field: str) -> None:
    payload = valid_document()
    payload.pop(field)

    with pytest.raises(ValueError, match=field):
        CorpusDocument.model_validate(payload)


def test_corpus_rejects_stale_content_hash() -> None:
    payload = valid_document()
    payload["text"] = f"{payload['text']}正文发生变化。"

    with pytest.raises(ValueError, match="content_hash does not match"):
        CorpusDocument.model_validate(payload)


def test_load_corpus_excludes_pending_extended_document(tmp_path) -> None:
    payload = valid_document()
    payload.update(
        {
            "source_tier": "extended",
            "review_status": "pending",
        }
    )
    (tmp_path / "pending.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    assert load_corpus(tmp_path) == []
