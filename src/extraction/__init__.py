"""LLM-based knowledge extraction."""

from src.extraction.models import (
    DocumentMetadata,
    Entity,
    EntityType,
    ExtractionResult,
    Relation,
    RelationType,
)

__all__ = [
    "BatchExtractionRunner",
    "BatchItemResult",
    "BatchReport",
    "DocumentMetadata",
    "Entity",
    "EntityType",
    "ExtractionResult",
    "Relation",
    "RelationType",
]


def __getattr__(name: str) -> object:
    if name in {"BatchExtractionRunner", "BatchItemResult", "BatchReport"}:
        from src.extraction.batch import BatchExtractionRunner, BatchItemResult, BatchReport

        exports = {
            "BatchExtractionRunner": BatchExtractionRunner,
            "BatchItemResult": BatchItemResult,
            "BatchReport": BatchReport,
        }
        return exports[name]
    raise AttributeError(name)
