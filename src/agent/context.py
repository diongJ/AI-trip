from __future__ import annotations

from src.agent.models import Citation, ToolResult
from src.preprocessing import CorpusDocument, load_corpus


def load_source_lookup(corpus_root: str = "data/raw") -> dict[str, CorpusDocument]:
    return {document.doc_id: document for document in load_corpus(corpus_root)}


def citations_from_result(
    result: ToolResult,
    *,
    max_citations: int = 6,
    source_lookup: dict[str, CorpusDocument] | None = None,
) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for hit in result.graph:
        key = (hit.document_id, hit.evidence)
        if key in seen:
            continue
        seen.add(key)
        source = source_lookup.get(hit.document_id) if source_lookup else None
        citations.append(
            Citation(
                doc_id=hit.document_id,
                title=source.title if source else _title_from_graph(hit.document_id),
                source_name=source.source_name if source else "知识图谱 V1",
                source_url=str(source.source_url) if source else "https://github.com/diongJ/AI-trip",
                evidence=hit.evidence,
            )
        )
        if len(citations) >= max_citations:
            return citations

    for hit in result.documents:
        doc_id = str(hit.metadata["doc_id"])
        evidence = hit.content
        key = (doc_id, evidence)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                doc_id=doc_id,
                title=str(hit.metadata["title"]),
                source_name=str(hit.metadata["source_name"]),
                source_url=str(hit.metadata["source_url"]),
                evidence=evidence,
            )
        )
        if len(citations) >= max_citations:
            return citations
    return citations


def build_grounded_context(result: ToolResult, *, max_chars: int = 3000) -> str:
    parts: list[str] = []
    for hit in result.graph:
        parts.append(
            "[KG] {source} -[{relation}]-> {target} ({doc_id})\n证据：{evidence}".format(
                source=hit.source_entity.name,
                relation=hit.relation,
                target=hit.target_entity.name,
                doc_id=hit.document_id,
                evidence=hit.evidence,
            )
        )
    for hit in result.documents:
        parts.append(
            "[DOC] {doc_id} {title}\n来源：{source_name} {source_url}\n片段：{content}".format(
                doc_id=hit.metadata["doc_id"],
                title=hit.metadata["title"],
                source_name=hit.metadata["source_name"],
                source_url=hit.metadata["source_url"],
                content=hit.content,
            )
        )
    context = "\n\n".join(parts)
    return context[:max_chars]


def _title_from_graph(document_id: str) -> str:
    return f"图谱关系证据 {document_id}"
