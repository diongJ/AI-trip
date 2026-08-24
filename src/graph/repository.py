from neo4j import Driver, GraphDatabase

from src.config.settings import Settings
from src.extraction.models import Entity, EntityType, ExtractionResult, Relation


class Neo4jKnowledgeGraph:
    def __init__(self, settings: Settings, *, driver: Driver | None = None) -> None:
        settings.require_neo4j()
        self.settings = settings
        self._owns_driver = driver is None
        self.driver = driver or GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password.get_secret_value()),
        )

    def close(self) -> None:
        if self._owns_driver:
            self.driver.close()

    def __enter__(self) -> "Neo4jKnowledgeGraph":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def ensure_constraints(self) -> None:
        query = "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE"
        self.driver.execute_query(query, database_=self.settings.neo4j_database)

    def upsert_extraction(self, result: ExtractionResult) -> None:
        self.ensure_constraints()
        with self.driver.session(database=self.settings.neo4j_database) as session:
            session.execute_write(self._write_extraction, result)

    def get_counts(self) -> dict[str, int]:
        records, _, _ = self.driver.execute_query(
            """
            CALL () { MATCH (n:Entity) RETURN count(n) AS entities }
            CALL () { MATCH (:Entity)-[r]->(:Entity) RETURN count(r) AS relations }
            RETURN entities, relations
            """,
            database_=self.settings.neo4j_database,
        )
        if not records:
            return {"entities": 0, "relations": 0}
        return {
            "entities": records[0]["entities"],
            "relations": records[0]["relations"],
        }

    def verify_extraction(self, result: ExtractionResult) -> dict[str, list[object]]:
        entity_ids = [entity.id for entity in result.entities]
        relation_rows = [
            {
                "source_id": relation.source_id,
                "relation": relation.relation.value,
                "target_id": relation.target_id,
                "document_id": relation.document_id,
                "evidence": relation.evidence,
            }
            for relation in result.relations
        ]
        entity_records, _, _ = self.driver.execute_query(
            """
            UNWIND $entity_ids AS entity_id
            OPTIONAL MATCH (n:Entity {id: entity_id})
            WITH entity_id, n WHERE n IS NULL
            RETURN collect(entity_id) AS missing_entities
            """,
            entity_ids=entity_ids,
            database_=self.settings.neo4j_database,
        )
        relation_records, _, _ = self.driver.execute_query(
            """
            UNWIND $relations AS expected
            OPTIONAL MATCH (source:Entity {id: expected.source_id})-[r]->
                           (target:Entity {id: expected.target_id})
            WHERE type(r) = expected.relation
              AND r.document_id = expected.document_id
              AND r.evidence = expected.evidence
            WITH expected, count(r) AS matches
            WHERE matches = 0
            RETURN collect(expected) AS missing_relations
            """,
            relations=relation_rows,
            database_=self.settings.neo4j_database,
        )
        return {
            "missing_entities": (
                entity_records[0]["missing_entities"] if entity_records else entity_ids
            ),
            "missing_relations": (
                relation_records[0]["missing_relations"] if relation_records else relation_rows
            ),
        }

    @classmethod
    def _write_extraction(cls, tx: object, result: ExtractionResult) -> None:
        for entity in result.entities:
            cls._upsert_entity(tx, entity)
        for relation in result.relations:
            cls._upsert_relation(tx, relation)

    @staticmethod
    def _upsert_entity(tx: object, entity: Entity) -> None:
        label = entity.type.value
        if label not in {item.value for item in EntityType}:
            raise ValueError(f"unsupported Neo4j label: {label}")
        query = f"""
        MERGE (n:Entity:`{label}` {{id: $id}})
        SET n.name = $name,
            n.entity_type = $entity_type,
            n.aliases = reduce(
                acc = coalesce(n.aliases, []), item IN $aliases |
                CASE WHEN item IN acc THEN acc ELSE acc + item END
            ),
            n.description = CASE
                WHEN $description <> '' THEN $description
                ELSE coalesce(n.description, '')
            END,
            n.source_ids = reduce(
                acc = coalesce(n.source_ids, []), item IN $source_ids |
                CASE WHEN item IN acc THEN acc ELSE acc + item END
            ),
            n.confidence = CASE
                WHEN n.confidence IS NULL OR $confidence > n.confidence THEN $confidence
                ELSE n.confidence
            END
        """
        tx.run(
            query,
            id=entity.id,
            name=entity.name,
            entity_type=entity.type.value,
            aliases=entity.aliases,
            description=entity.description,
            source_ids=entity.source_ids,
            confidence=entity.confidence,
        ).consume()

    @staticmethod
    def _upsert_relation(tx: object, relation: Relation) -> None:
        relation_type = relation.relation.value
        query = f"""
        MATCH (source:Entity {{id: $source_id}})
        MATCH (target:Entity {{id: $target_id}})
        MERGE (source)-[r:`{relation_type}` {{document_id: $document_id}}]->(target)
        SET r.evidence = $evidence,
            r.confidence = $confidence
        """
        summary = tx.run(
            query,
            source_id=relation.source_id,
            target_id=relation.target_id,
            document_id=relation.document_id,
            evidence=relation.evidence,
            confidence=relation.confidence,
        ).consume()
        if summary.counters.relationships_created == 0:
            # Zero is valid on an idempotent rerun; missing endpoints are caught below.
            check = tx.run(
                "MATCH (n:Entity) WHERE n.id IN [$source_id, $target_id] RETURN count(n) AS count",
                source_id=relation.source_id,
                target_id=relation.target_id,
            ).single()
            if check is None or check["count"] != 2:
                raise ValueError(
                    f"cannot create {relation_type}: source or target entity is missing"
                )

    def fetch_paths(self, entity_ids: list[str]) -> list[dict[str, object]]:
        records, _, _ = self.driver.execute_query(
            """
            MATCH (source:Entity)-[r]->(target:Entity)
            WHERE source.id IN $entity_ids OR target.id IN $entity_ids
            RETURN source.id AS source_id, type(r) AS relation, target.id AS target_id,
                   r.document_id AS document_id, r.evidence AS evidence
            ORDER BY source_id, relation, target_id
            """,
            entity_ids=entity_ids,
            database_=self.settings.neo4j_database,
        )
        return [record.data() for record in records]
