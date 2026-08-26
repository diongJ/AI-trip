from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from src.agent.models import ToolResult
from src.rag.models import GraphHit, RetrievalHit


class DocumentRetriever(Protocol):
    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
        min_score: float = 0.0,
    ) -> list[RetrievalHit]: ...

    def search_many(
        self,
        queries: list[str],
        *,
        top_k: int = 8,
        per_query_k: int = 12,
        category: str | None = None,
        source_tier: str | None = None,
    ) -> list[RetrievalHit]: ...


class GraphRetriever(Protocol):
    def list_entities(
        self,
        query: str = "",
        *,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[GraphEntity]: ...

    def resolve_entity_id(self, query: str) -> str | None: ...

    def get_neighbors(
        self,
        entity_query: str,
        *,
        depth: int = 1,
        limit: int = 20,
    ) -> list[GraphHit]: ...


RELATION_HINTS: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = (
    (re.compile(r"材料|材质"), frozenset({"MADE_OF"})),
    (re.compile(r"纹饰|图案"), frozenset({"HAS_PATTERN"})),
    (re.compile(r"出土"), frozenset({"EXCAVATED_FROM"})),
    (re.compile(r"埋葬|墓葬|葬于"), frozenset({"BURIED_IN"})),
    (re.compile(r"类别|种类"), frozenset({"BELONGS_TO_CATEGORY"})),
    (re.compile(r"朝代|时期|年代|制作于"), frozenset({"CREATED_IN"})),
    (re.compile(r"文化|反映"), frozenset({"REFLECTS_CULTURE"})),
    (re.compile(r"属于哪国|哪个国家|所属国家"), frozenset({"BELONGS_TO_STATE"})),
)


@dataclass
class AgentTools:
    document_retriever: DocumentRetriever
    graph_retriever: GraphRetriever

    def search_documents(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
        queries: list[str] | None = None,
    ) -> ToolResult:
        documents = (
            self.document_retriever.search_many(queries, top_k=top_k, category=category)
            if queries and hasattr(self.document_retriever, "search_many")
            else self.document_retriever.search(query, top_k=top_k, category=category)
        )
        return ToolResult(documents=documents)

    def search_kg(
        self,
        query: str,
        *,
        entity_query: str | None = None,
        depth: int = 1,
        limit: int = 12,
        entity_queries: list[str] | None = None,
    ) -> ToolResult:
        hits: list[GraphHit] = []
        seen: set[tuple[str, str, str, str]] = set()
        for candidate in entity_queries or [entity_query or query]:
            for hit in self.graph_retriever.get_neighbors(candidate, depth=depth, limit=limit):
                key = (hit.source_entity.id, hit.relation, hit.target_entity.id, hit.document_id)
                if key not in seen:
                    seen.add(key)
                    hits.append(hit)
        return ToolResult(
            graph=_filter_relevant_relations(query, hits)
        )

    def hybrid_search(
        self,
        query: str,
        *,
        entity_query: str | None = None,
        top_k: int = 5,
        depth: int = 1,
        limit: int = 12,
        queries: list[str] | None = None,
        entity_queries: list[str] | None = None,
    ) -> ToolResult:
        graph = self.search_kg(
            query,
            entity_query=entity_query,
            entity_queries=entity_queries,
            depth=depth,
            limit=limit,
        ).graph if (entity_query or entity_queries) else []
        documents = (
            self.document_retriever.search_many(queries, top_k=top_k)
            if queries and hasattr(self.document_retriever, "search_many")
            else self.document_retriever.search(query, top_k=top_k)
        )
        return ToolResult(documents=documents, graph=graph)


def _filter_relevant_relations(query: str, hits: list[GraphHit]) -> list[GraphHit]:
    expected: set[str] = set()
    for pattern, relations in RELATION_HINTS:
        if pattern.search(query):
            expected.update(relations)
    if not expected:
        return hits
    return [hit for hit in hits if hit.relation in expected]
