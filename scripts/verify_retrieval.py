from __future__ import annotations

import json

from scripts.build_graph_v1 import main as build_graph
from src.graph.retriever import LocalGraphRetriever
from src.rag.index import build_rag_index
from src.rag.retriever import RagRetriever


def main() -> None:
    build_rag_index(force=True)
    build_graph()
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


if __name__ == "__main__":
    main()
