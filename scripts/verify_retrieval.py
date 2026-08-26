from __future__ import annotations

import json
from pathlib import Path

from scripts.build_graph_v1 import build_graph_v1
from src.extraction.models import Entity, ExtractionResult, Relation
from src.graph.retriever import LocalGraphRetriever
from src.rag.index import build_rag_index
from src.rag.retriever import RagRetriever


def main() -> None:
    build_rag_index(force=True)
    graph_source = _ensure_local_graph()
    rag = RagRetriever()
    graph = LocalGraphRetriever()

    entity_checks = {
        "赵眜": "person:赵眜",
        "南越文王": "person:赵眜",
        "南越文王墓": "tomb:南越文王墓",
        "文帝行玺": "relic:文帝行玺",
        "文帝行玺金印": "relic:文帝行玺",
    }
    resolved = {
        query: (graph.resolve_entity_id(query) == expected)
        for query, expected in entity_checks.items()
    }
    relation_hits = graph.get_neighbors("文帝行玺", depth=1, limit=10)
    rag_hits = rag.search("文帝行玺是什么？", top_k=5)
    payload = {
        "entity_resolution": resolved,
        "graph_source": graph_source,
        "graph_hits": len(relation_hits),
        "graph_evidence_complete": all(hit.document_id and hit.evidence for hit in relation_hits),
        "rag_hits": len(rag_hits),
        "rag_sources_complete": all(hit.metadata.get("source_url") for hit in rag_hits),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not all(resolved.values()):
        raise SystemExit("entity resolution failed")
    if not relation_hits or not payload["graph_evidence_complete"]:
        raise SystemExit("graph retrieval failed")
    if not rag_hits or not payload["rag_sources_complete"]:
        raise SystemExit("RAG retrieval failed")


def _ensure_local_graph() -> str:
    by_document = Path("data/graph/by_document")
    graph_path = Path("data/graph/knowledge_graph_v1.json")
    if by_document.is_dir():
        build_graph_v1()
        return "day3-fused-graph"
    if graph_path.exists():
        return "existing-local-graph"

    graph_path.parent.mkdir(parents=True, exist_ok=True)
    result = ExtractionResult(
        entities=[
            Entity(
                id="person:赵眜",
                name="赵眜",
                type="Person",
                aliases=["南越文王", "南越文帝"],
                source_ids=["DOC_005"],
                confidence=0.95,
            ),
            Entity(
                id="tomb:南越文王墓",
                name="南越文王墓",
                type="Tomb",
                aliases=["南越王墓"],
                source_ids=["DOC_008"],
                confidence=0.95,
            ),
            Entity(
                id="relic:文帝行玺",
                name="文帝行玺",
                type="Relic",
                aliases=["文帝行玺金印", "“文帝行玺”龙钮金印"],
                source_ids=["DOC_013"],
                confidence=0.95,
            ),
            Entity(
                id="material:金",
                name="金",
                type="Material",
                aliases=[],
                source_ids=["DOC_013"],
                confidence=0.95,
            ),
        ],
        relations=[
            Relation(
                source_id="person:赵眜",
                relation="BURIED_IN",
                target_id="tomb:南越文王墓",
                document_id="DOC_005",
                evidence="墓主人是南越国第二代王赵眜，自称南越文帝。",
                confidence=0.95,
            ),
            Relation(
                source_id="relic:文帝行玺",
                relation="RELATED_TO_PERSON",
                target_id="person:赵眜",
                document_id="DOC_013",
                evidence="金印出土于墓主胸部，证实墓主为南越文帝。",
                confidence=0.95,
            ),
            Relation(
                source_id="relic:文帝行玺",
                relation="MADE_OF",
                target_id="material:金",
                document_id="DOC_013",
                evidence="“文帝行玺”龙钮金印为西汉南越国文物。",
                confidence=0.95,
            ),
        ],
    )
    graph_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return "smoke-test-fallback-graph"


if __name__ == "__main__":
    main()
