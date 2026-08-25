from __future__ import annotations

import json
from pathlib import Path

from src.rag.index import build_rag_index
from src.rag.retriever import RagRetriever


QUESTIONS = [
    ("文帝行玺是什么？", ["文帝行玺", "金印"]),
    ("赵眜是谁？", ["赵眜", "南越文王", "墓主人"]),
    ("南越文王墓如何发现？", ["南越文王墓", "1983", "墓"]),
    ("丝缕玉衣有什么特点？", ["丝缕玉衣", "玉衣"]),
    ("犀角形玉杯是什么材质？", ["犀角形玉杯", "玉杯", "青玉"]),
    ("南越国是谁建立的？", ["赵佗", "南越国"]),
    ("铜印花板模有什么用途？", ["铜印花板模", "印染", "丝织物"]),
    ("船纹铜提筒反映了什么？", ["船纹铜提筒", "水上交通", "船纹"]),
    ("王墓展区在哪里？", ["王墓展区", "解放北路"]),
    ("今天馆内有多少游客？", None),
]


def main() -> None:
    build_rag_index(force=True)
    retriever = RagRetriever()
    rows = []
    relevant_count = 0
    for index, (question, expected_terms) in enumerate(QUESTIONS, start=1):
        hits = retriever.search(question, top_k=5)
        relevant = _is_relevant(hits, expected_terms)
        if relevant:
            relevant_count += 1
        rows.append(
            {
                "id": index,
                "question": question,
                "rag_top5_relevant": relevant,
                "top_doc_ids": [hit.metadata["doc_id"] for hit in hits],
                "sources_complete": all(
                    hit.metadata.get("source_url") and hit.metadata.get("title")
                    for hit in hits
                ),
            }
        )
    output_path = Path("docs/day4_retrieval_smoke_test.md")
    output_path.write_text(_markdown(rows, relevant_count), encoding="utf-8")
    print(json.dumps({"questions": len(rows), "rag_relevant": relevant_count}, ensure_ascii=False))
    if relevant_count < 8:
        raise SystemExit("RAG smoke test failed: fewer than 8 relevant Top-5 results")


def _is_relevant(hits: object, expected_terms: list[str] | None) -> bool:
    if expected_terms is None:
        return False
    if not expected_terms:
        return True
    combined = "\n".join(hit.content + " " + str(hit.metadata) for hit in hits)
    return any(term in combined for term in expected_terms)


def _markdown(rows: list[dict[str, object]], relevant_count: int) -> str:
    lines = [
        "# Day 4 检索手测记录",
        "",
        f"RAG Top-5 人工规则相关数：{relevant_count}/10。",
        "",
        "| 编号 | 问题 | RAG Top-5 是否相关 | 来源是否完整 | Top 文档 | 备注 |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {id} | {question} | {relevant} | {sources} | {docs} | 自动 smoke 记录 |".format(
                id=row["id"],
                question=row["question"],
                relevant="是" if row["rag_top5_relevant"] else "否/超范围",
                sources="是" if row["sources_complete"] else "否",
                docs=", ".join(row["top_doc_ids"]),
            )
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
