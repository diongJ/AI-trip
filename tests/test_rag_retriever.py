import json

from src.rag.index import build_rag_index
from src.rag.retriever import RagRetriever


def write_doc(root, doc_id: str, title: str, category: str, text: str) -> None:
    path = root / category / f"{doc_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "doc_id": doc_id,
                "title": title,
                "source_name": "南越王博物院",
                "source_url": "https://www.nywmuseum.org.cn/",
                "source_type": "official",
                "category": category,
                "retrieved_at": "2026-08-23",
                "text": text,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_rag_retriever_returns_ranked_sources(tmp_path) -> None:
    corpus = tmp_path / "raw"
    index = tmp_path / "index"
    write_doc(corpus, "DOC_001", "文帝行玺", "relic", "文帝行玺是南越文王墓出土的金印，印面阴刻小篆文字。")
    write_doc(corpus, "DOC_002", "王墓展区", "museum", "王墓展区位于广州市越秀区，是南越王博物院的重要展区。")
    build_rag_index(corpus_root=corpus, index_dir=index, force=True, chunk_size=80)

    hits = RagRetriever(index).search("文帝行玺是什么", top_k=2)

    assert hits
    assert hits[0].rank == 1
    assert hits[0].metadata["doc_id"] == "DOC_001"
    assert hits[0].metadata["source_url"]


def test_rag_retriever_category_filter(tmp_path) -> None:
    corpus = tmp_path / "raw"
    index = tmp_path / "index"
    write_doc(corpus, "DOC_001", "文帝行玺", "relic", "文帝行玺是南越文王墓出土的金印，印面阴刻小篆文字。")
    write_doc(corpus, "DOC_002", "南越文王墓", "tomb", "南越文王墓出土文帝行玺，是重要的汉代彩绘石室墓。")
    build_rag_index(corpus_root=corpus, index_dir=index, force=True, chunk_size=80)

    hits = RagRetriever(index).search("文帝行玺", top_k=5, category="tomb")

    assert [hit.metadata["category"] for hit in hits] == ["tomb"]


def test_rag_retriever_empty_query_returns_no_hits(tmp_path) -> None:
    corpus = tmp_path / "raw"
    index = tmp_path / "index"
    write_doc(corpus, "DOC_001", "文帝行玺", "relic", "文帝行玺是南越文王墓出土的金印，印面阴刻小篆文字。")
    build_rag_index(corpus_root=corpus, index_dir=index, force=True, chunk_size=80)

    assert RagRetriever(index).search("火星基地", top_k=5) == []
