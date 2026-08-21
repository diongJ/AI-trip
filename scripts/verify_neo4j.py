import sys

from neo4j.exceptions import Neo4jError

from src.config import get_settings
from src.config.settings import ConfigurationError
from src.extraction.models import Entity, EntityType, ExtractionResult, Relation, RelationType
from src.graph import Neo4jKnowledgeGraph


TEST_SOURCE_ID = "test:day1-source"
TEST_TARGET_ID = "test:day1-target"


def build_test_result() -> ExtractionResult:
    return ExtractionResult(
        entities=[
            Entity(
                id=TEST_SOURCE_ID,
                name="Day 1 测试墓葬",
                type=EntityType.TOMB,
                aliases=[],
                description="连接测试使用，脚本结束后删除。",
                source_ids=["DOC_CONNECTION_TEST"],
                confidence=1,
            ),
            Entity(
                id=TEST_TARGET_ID,
                name="Day 1 测试墓室",
                type=EntityType.TOMB_CHAMBER,
                aliases=[],
                description="连接测试使用，脚本结束后删除。",
                source_ids=["DOC_CONNECTION_TEST"],
                confidence=1,
            ),
        ],
        relations=[
            Relation(
                source_id=TEST_SOURCE_ID,
                relation=RelationType.CONTAINS,
                target_id=TEST_TARGET_ID,
                evidence="Day 1 Neo4j 连接测试。",
                document_id="DOC_CONNECTION_TEST",
                confidence=1,
            )
        ],
    )


def main() -> None:
    with Neo4jKnowledgeGraph(get_settings()) as graph:
        graph.verify_connectivity()
        result = build_test_result()
        try:
            graph.upsert_extraction(result)
            graph.upsert_extraction(result)
            records, _, _ = graph.driver.execute_query(
                """
                MATCH (a:Entity {id: $source_id})-[r:CONTAINS]->(b:Entity {id: $target_id})
                RETURN count(a) AS source_count, count(r) AS relation_count, count(b) AS target_count
                """,
                source_id=TEST_SOURCE_ID,
                target_id=TEST_TARGET_ID,
                database_=graph.settings.neo4j_database,
            )
            record = records[0]
            assert record["source_count"] == 1
            assert record["relation_count"] == 1
            assert record["target_count"] == 1
            print("Neo4j validation passed: connection, write, query and idempotency are valid")
        finally:
            graph.driver.execute_query(
                "MATCH (n:Entity) WHERE n.id IN $ids DETACH DELETE n",
                ids=[TEST_SOURCE_ID, TEST_TARGET_ID],
                database_=graph.settings.neo4j_database,
            )


if __name__ == "__main__":
    try:
        main()
    except (ConfigurationError, Neo4jError) as exc:
        print(f"Neo4j validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
