from __future__ import annotations

from dataclasses import dataclass

from src.agent.models import ToolResult
from src.graph.retriever import LocalGraphRetriever
from src.rag.retriever import RagRetriever


@dataclass
class AgentTools:
    document_retriever: RagRetriever
    graph_retriever: LocalGraphRetriever

    def search_documents(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
    ) -> ToolResult:
        return ToolResult(
            documents=self.document_retriever.search(
                query,
                top_k=top_k,
                category=category,
            )
        )

    def search_kg(
        self,
        entity_query: str,
        *,
        depth: int = 1,
        limit: int = 12,
    ) -> ToolResult:
        return ToolResult(
            graph=self.graph_retriever.get_neighbors(
                entity_query,
                depth=depth,
                limit=limit,
            )
        )

    def hybrid_search(
        self,
        query: str,
        *,
        entity_query: str | None = None,
        top_k: int = 5,
        depth: int = 1,
        limit: int = 12,
    ) -> ToolResult:
        graph = []
        if entity_query:
            graph = self.graph_retriever.get_neighbors(
                entity_query,
                depth=depth,
                limit=limit,
            )
        documents = self.document_retriever.search(query, top_k=top_k)
        return ToolResult(documents=documents, graph=graph)
