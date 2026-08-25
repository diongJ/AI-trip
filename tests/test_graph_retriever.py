from pathlib import Path

import pytest
from pydantic import ValidationError

from src.extraction.models import Entity, ExtractionResult, Relation
from src.graph.retriever import LocalGraphRetriever
from src.rag.models import GraphEntity, GraphHit


def test_local_graph_resolves_aliases(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_test_graph(Path("data/graph/knowledge_graph_v1.json"))

    retriever = LocalGraphRetriever(Path("data/graph/knowledge_graph_v1.json"))

    assert retriever.resolve_entity_id("赵眜") == "person:赵眜"
    assert retriever.resolve_entity_id("南越文王") == "person:赵眜"
    assert retriever.resolve_entity_id("文帝行玺金印") == "relic:文帝行玺"


def test_local_graph_returns_evidence_bearing_relations(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_test_graph(Path("data/graph/knowledge_graph_v1.json"))

    hits = LocalGraphRetriever(Path("data/graph/knowledge_graph_v1.json")).get_neighbors(
        "文帝行玺", depth=1
    )

    assert hits
    assert all(hit.document_id and hit.evidence for hit in hits)
    assert any(hit.relation == "MADE_OF" for hit in hits)


def test_graph_hit_rejects_missing_document_id() -> None:
    with pytest.raises(ValidationError, match="document_id"):
        GraphHit(
            source_entity=GraphEntity(id="a", name="A", type="Relic"),
            relation="MADE_OF",
            target_entity=GraphEntity(id="b", name="B", type="Material"),
            direction="outgoing",
            document_id="",
            evidence="原文证据",
            backend="local-json",
        )


def write_test_graph(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = ExtractionResult(
        entities=[
            Entity(
                id="person:赵眜",
                name="赵眜",
                type="Person",
                aliases=["南越文王"],
                source_ids=["DOC_005"],
                confidence=0.95,
            ),
            Entity(
                id="relic:文帝行玺",
                name="文帝行玺",
                type="Relic",
                aliases=["文帝行玺金印"],
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
                source_id="relic:文帝行玺",
                relation="MADE_OF",
                target_id="material:金",
                document_id="DOC_013",
                evidence="文帝行玺为金印。",
                confidence=0.95,
            )
        ],
    )
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
