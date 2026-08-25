"""Graph fusion, persistence, and retrieval helpers."""

from src.graph.fusion import FusionReport, ResolutionConfig, fuse_extractions
from src.graph.retriever import LocalGraphRetriever, Neo4jGraphRetriever

__all__ = [
    "FusionReport",
    "LocalGraphRetriever",
    "Neo4jGraphRetriever",
    "Neo4jKnowledgeGraph",
    "ResolutionConfig",
    "fuse_extractions",
]


def __getattr__(name: str) -> object:
    if name == "Neo4jKnowledgeGraph":
        from src.graph.repository import Neo4jKnowledgeGraph

        return Neo4jKnowledgeGraph
    raise AttributeError(name)
