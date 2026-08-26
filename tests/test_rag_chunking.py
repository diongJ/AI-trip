from src.preprocessing import CorpusDocument
from src.rag.chunking import split_corpus, split_document
from hashlib import sha256


def document(doc_id: str = "DOC_001", text: str | None = None) -> CorpusDocument:
    body = text or "文帝行玺是南越文王墓出土的金印。印面阴刻小篆文字。"
    return CorpusDocument(
        doc_id=doc_id,
        title="文帝行玺",
        source_name="南越王博物院",
        source_url="https://www.nywmuseum.org.cn/",
        source_type="official",
        category="relic",
        retrieved_at="2026-08-23",
        text=body,
        evidence_role="factual",
        content_hash=sha256(body.encode("utf-8")).hexdigest(),
        review_status="approved",
    )


def test_split_document_is_deterministic() -> None:
    first = split_document(document(), chunk_size=30, chunk_overlap=5)
    second = split_document(document(), chunk_size=30, chunk_overlap=5)

    assert [chunk.model_dump() for chunk in first] == [chunk.model_dump() for chunk in second]


def test_split_corpus_does_not_cross_documents() -> None:
    chunks = split_corpus(
        [
            document("DOC_001", "文帝行玺是南越文王墓出土的金印，印面阴刻小篆文字。"),
            document("DOC_002", "丝缕玉衣由大量玉片和丝缕编缀而成，是重要的丧葬文物。"),
        ],
        chunk_size=30,
        chunk_overlap=3,
    )

    assert {chunk.doc_id for chunk in chunks} == {"DOC_001", "DOC_002"}
    assert all(chunk.chunk_id.startswith(chunk.doc_id) for chunk in chunks)


def test_chunk_metadata_is_complete() -> None:
    chunk = split_document(document())[0]

    assert chunk.chunk_id == "DOC_001_CHUNK_001"
    assert chunk.doc_id == "DOC_001"
    assert chunk.title == "文帝行玺"
    assert chunk.source_name == "南越王博物院"
    assert str(chunk.source_url).startswith("https://")
