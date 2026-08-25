from pathlib import Path

import pytest
from pydantic import ValidationError

from src.extraction.models import Entity, ExtractionResult, Relation
from src.graph.retriever import LocalGraphRetriever, Neo4jGraphRetriever
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


def test_neo4j_retriever_resolves_entities_and_unwinds_two_hop_paths() -> None:
    driver = FakeDriver()
    retriever = Neo4jGraphRetriever(FakeGraph(driver))

    assert retriever.resolve_entity_id("文帝行玺") == "relic:文帝行玺"
    assert retriever.resolve_entity_id("文帝行玺是什么材料") == "relic:文帝行玺"
    assert retriever.resolve_entity_id("文帝行玺金印") == "relic:文帝行玺"
    assert driver.supports_embedded_entity_query
    hits = retriever.get_neighbors("文帝行玺", depth=2)

    assert {hit.relation for hit in hits} == {"MADE_OF", "CREATED_IN"}
    assert driver.used_two_hop_unwind


class FakeRecord:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def data(self) -> dict[str, object]:
        return self.payload


class FakeDriver:
    def __init__(self) -> None:
        self.used_two_hop_unwind = False
        self.supports_embedded_entity_query = False

    def execute_query(self, cypher: str, **parameters: object) -> tuple[list[FakeRecord], None, None]:
        if "RETURN entity.id AS id" in cypher:
            self.supports_embedded_entity_query = (
                "toLower($query) CONTAINS toLower(entity.name)" in cypher
            )
            uses_legacy_alias = "金印" in str(parameters.get("query", ""))
            return (
                [
                    FakeRecord(
                        {
                            "id": "relic:文帝行玺金印" if uses_legacy_alias else "relic:文帝行玺",
                            "name": "文帝行玺金印" if uses_legacy_alias else "文帝行玺",
                            "type": "Relic",
                            "aliases": ["文帝行玺"] if uses_legacy_alias else ["文帝行玺金印"],
                        }
                    )
                ],
                None,
                None,
            )
        self.used_two_hop_unwind = (
            "[*1..2]" in cypher and "UNWIND relationships(path) AS r" in cypher
        )
        return (
            [
                FakeRecord(
                    relation_record(
                        "relic:文帝行玺",
                        "文帝行玺",
                        "Relic",
                        "MADE_OF",
                        "material:金",
                        "金",
                        "Material",
                    )
                ),
                FakeRecord(
                    relation_record(
                        "material:金",
                        "金",
                        "Material",
                        "CREATED_IN",
                        "dynasty:西汉",
                        "西汉",
                        "Dynasty",
                    )
                ),
            ],
            None,
            None,
        )


class FakeSettings:
    neo4j_database = "neo4j"


class FakeGraph:
    def __init__(self, driver: FakeDriver) -> None:
        self.driver = driver
        self.settings = FakeSettings()


def relation_record(
    source_id: str,
    source_name: str,
    source_type: str,
    relation: str,
    target_id: str,
    target_name: str,
    target_type: str,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "source_name": source_name,
        "source_type": source_type,
        "source_aliases": [],
        "relation": relation,
        "target_id": target_id,
        "target_name": target_name,
        "target_type": target_type,
        "target_aliases": [],
        "direction": "outgoing",
        "document_id": "DOC_013",
        "evidence": "测试证据",
    }


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
