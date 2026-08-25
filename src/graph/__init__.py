"""Neo4j persistence for validated knowledge graph data."""

from src.graph.retriever import LocalGraphRetriever, Neo4jGraphRetriever

__all__ = ["LocalGraphRetriever", "Neo4jGraphRetriever", "Neo4jKnowledgeGraph"]


def __getattr__(name: str) -> object:
    if name == "Neo4jKnowledgeGraph":
        from src.graph.repository import Neo4jKnowledgeGraph

        return Neo4jKnowledgeGraph
    raise AttributeError(name)

