from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.build_graph_v1 import main as build_graph
from src.graph.retriever import LocalGraphRetriever
from src.rag.models import GraphEntity, GraphHit


def test_local_graph_resolves_aliases(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    build_graph()

    retriever = LocalGraphRetriever(Path("data/graph/knowledge_graph_v1.json"))

    assert retriever.resolve_entity_id("赵眜") == "person:赵眜"
    assert retriever.resolve_entity_id("南越文王") == "person:赵眜"
    assert retriever.resolve_entity_id("文帝行玺金印") == "relic:文帝行玺"


def test_local_graph_returns_evidence_bearing_relations(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    build_graph()

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
