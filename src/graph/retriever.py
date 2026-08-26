from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

from src.extraction.models import Entity, ExtractionResult, Relation
from src.graph.fusion import ResolutionConfig
from src.rag.models import GraphEntity, GraphHit

if TYPE_CHECKING:
    from src.graph.repository import Neo4jKnowledgeGraph

try:
    from neo4j.exceptions import Neo4jError
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal installs
    Neo4jError = Exception

DEFAULT_GRAPH_PATH = Path("data/graph/knowledge_graph_v1.json")
DEFAULT_RESOLUTION_PATH = Path("data/curated/entity_resolution_v1.json")


class GraphRetrievalError(RuntimeError):
    pass


class LocalGraphRetriever:
    def __init__(self, graph_path: str | Path = DEFAULT_GRAPH_PATH) -> None:
        path = Path(graph_path)
        if not path.exists():
            raise GraphRetrievalError(
                f"local graph is missing: {path}. Run python -m scripts.build_graph_v1 first."
            )
        result = ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))
        self.entities = {entity.id: entity for entity in result.entities}
        self.relations = result.relations
        self.alias_index = _build_alias_index(result.entities)

    def search_entities(self, query: str, *, limit: int = 5) -> list[GraphEntity]:
        normalized = _normalize_name(query)
        if not normalized:
            return []
        exact = self.alias_index.get(normalized)
        matches: list[Entity] = []
        if exact:
            matches.append(self.entities[exact])
        for entity in self.entities.values():
            names = [_normalize_name(entity.name), *[_normalize_name(alias) for alias in entity.aliases]]
            if entity not in matches and any(normalized in name or name in normalized for name in names):
                matches.append(entity)
            if len(matches) >= limit:
                break
        return [_graph_entity(entity) for entity in matches[:limit]]

    def list_entities(
        self,
        query: str = "",
        *,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[GraphEntity]:
        """List graph entities for read-only browsing, with optional filtering."""
        if limit <= 0:
            raise ValueError("limit must be positive")
        normalized = _normalize_name(query)
        matches = []
        for entity in self.entities.values():
            if entity_type and entity.type.value != entity_type:
                continue
            searchable = [entity.name, entity.id, *entity.aliases]
            if normalized and not any(
                normalized in _normalize_name(value) for value in searchable
            ):
                continue
            matches.append(entity)
        matches.sort(
            key=lambda entity: (
                0 if normalized and _normalize_name(entity.name) == normalized else 1,
                entity.type.value,
                entity.name,
                entity.id,
            )
        )
        return [_graph_entity(entity) for entity in matches[:limit]]

    def resolve_entity_id(self, query: str) -> str | None:
        matches = self.search_entities(query, limit=1)
        return matches[0].id if matches else None

    def get_neighbors(
        self,
        entity_query: str,
        *,
        depth: int = 1,
        limit: int = 20,
    ) -> list[GraphHit]:
        if depth not in {1, 2}:
            raise ValueError("depth must be 1 or 2")
        start_id = self.resolve_entity_id(entity_query)
        if start_id is None:
            return []

        hits: list[GraphHit] = []
        seen_relations: set[tuple[str, str, str, str]] = set()
        queue: deque[tuple[str, int]] = deque([(start_id, 0)])
        visited: set[str] = {start_id}
        while queue and len(hits) < limit:
            entity_id, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            for relation in self.relations:
                if len(hits) >= limit:
                    break
                if relation.source_id == entity_id:
                    hit = self._relation_to_hit(relation, "outgoing")
                    next_id = relation.target_id
                elif relation.target_id == entity_id:
                    hit = self._relation_to_hit(relation, "incoming")
                    next_id = relation.source_id
                else:
                    continue
                key = (
                    hit.source_entity.id,
                    hit.relation,
                    hit.target_entity.id,
                    hit.document_id,
                )
                if key not in seen_relations:
                    seen_relations.add(key)
                    hits.append(hit)
                if current_depth + 1 < depth and next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, current_depth + 1))
        return hits

    def _relation_to_hit(self, relation: Relation, direction: str) -> GraphHit:
        source = self.entities[relation.source_id]
        target = self.entities[relation.target_id]
        return GraphHit(
            source_entity=_graph_entity(source),
            relation=relation.relation.value,
            target_entity=_graph_entity(target),
            direction=direction,
            document_id=relation.document_id,
            evidence=relation.evidence,
            backend="local-json",
        )


class Neo4jGraphRetriever:
    def __init__(
        self,
        graph: "Neo4jKnowledgeGraph",
        *,
        resolution_path: str | Path = DEFAULT_RESOLUTION_PATH,
    ) -> None:
        self.graph = graph
        path = Path(resolution_path)
        self.canonical_id_map = (
            ResolutionConfig.from_path(path).canonical_id_map if path.exists() else {}
        )

    def search_entities(self, query: str, *, limit: int = 5) -> list[GraphEntity]:
        records, _, _ = self.graph.driver.execute_query(
            """
            MATCH (entity:Entity)
            WHERE toLower(entity.name) CONTAINS toLower($query)
               OR toLower($query) CONTAINS toLower(entity.name)
               OR any(
                   alias IN coalesce(entity.aliases, [])
                   WHERE toLower(alias) CONTAINS toLower($query)
                      OR toLower($query) CONTAINS toLower(alias)
               )
            RETURN entity.id AS id, entity.name AS name, entity.entity_type AS type,
                   coalesce(entity.aliases, []) AS aliases
            ORDER BY CASE WHEN toLower(entity.name) = toLower($query) THEN 0 ELSE 1 END,
                     size(entity.name) DESC,
                     name
            LIMIT $limit
            """,
            query=query,
            limit=limit,
            database_=self.graph.settings.neo4j_database,
        )
        return [GraphEntity.model_validate(record.data()) for record in records]

    def list_entities(
        self,
        query: str = "",
        *,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[GraphEntity]:
        """List graph entities for read-only browsing, with optional filtering."""
        if limit <= 0:
            raise ValueError("limit must be positive")
        records, _, _ = self.graph.driver.execute_query(
            """
            MATCH (entity:Entity)
            WHERE ($query = ''
                   OR toLower(entity.name) CONTAINS toLower($query)
                   OR any(alias IN coalesce(entity.aliases, [])
                          WHERE toLower(alias) CONTAINS toLower($query)))
              AND ($entity_type IS NULL OR entity.entity_type = $entity_type)
            RETURN entity.id AS id, entity.name AS name, entity.entity_type AS type,
                   coalesce(entity.aliases, []) AS aliases
            ORDER BY CASE WHEN toLower(entity.name) = toLower($query) THEN 0 ELSE 1 END,
                     type, name, id
            LIMIT $limit
            """,
            query=query.strip(),
            entity_type=entity_type,
            limit=limit,
            database_=self.graph.settings.neo4j_database,
        )
        return [GraphEntity.model_validate(record.data()) for record in records]

    def resolve_entity_id(self, query: str) -> str | None:
        matches = self.search_entities(query, limit=5)
        if not matches:
            return None
        return _resolve_canonical_id(matches[0].id, self.canonical_id_map)

    def get_neighbors(
        self,
        entity_query: str,
        *,
        depth: int = 1,
        limit: int = 20,
    ) -> list[GraphHit]:
        if depth not in {1, 2}:
            raise ValueError("depth must be 1 or 2")
        entity_id = self.resolve_entity_id(entity_query)
        if entity_id is None:
            return []
        max_hops = "1..2" if depth == 2 else "1"
        records, _, _ = self.graph.driver.execute_query(
            f"""
            MATCH (start:Entity {{id: $entity_id}})
            MATCH path = (start)-[*{max_hops}]-(neighbor:Entity)
            UNWIND relationships(path) AS r
            WITH DISTINCT r, start
            WITH startNode(r) AS source, r, endNode(r) AS target,
                 CASE
                     WHEN startNode(r).id = start.id THEN 'outgoing'
                     WHEN endNode(r).id = start.id THEN 'incoming'
                     ELSE 'outgoing'
                 END AS direction
            RETURN source.id AS source_id, source.name AS source_name, source.entity_type AS source_type,
                   coalesce(source.aliases, []) AS source_aliases,
                   type(r) AS relation,
                   target.id AS target_id, target.name AS target_name, target.entity_type AS target_type,
                   coalesce(target.aliases, []) AS target_aliases,
                   direction AS direction,
                   r.document_id AS document_id,
                   r.evidence AS evidence
            ORDER BY source_id, relation, target_id, document_id
            LIMIT $limit
            """,
            entity_id=entity_id,
            limit=limit,
            database_=self.graph.settings.neo4j_database,
        )
        return [_record_to_graph_hit(record.data(), backend="neo4j") for record in records]


def get_graph_retriever(
    graph: "Neo4jKnowledgeGraph | None" = None,
    *,
    local_graph_path: str | Path = DEFAULT_GRAPH_PATH,
) -> LocalGraphRetriever | Neo4jGraphRetriever:
    if graph is not None:
        try:
            graph.verify_connectivity()
            return Neo4jGraphRetriever(graph)
        except Neo4jError:
            pass
    return LocalGraphRetriever(local_graph_path)


def _record_to_graph_hit(record: dict[str, object], *, backend: str) -> GraphHit:
    return GraphHit(
        source_entity=GraphEntity(
            id=str(record["source_id"]),
            name=str(record["source_name"]),
            type=str(record["source_type"]),
            aliases=list(record["source_aliases"]),
        ),
        relation=str(record["relation"]),
        target_entity=GraphEntity(
            id=str(record["target_id"]),
            name=str(record["target_name"]),
            type=str(record["target_type"]),
            aliases=list(record["target_aliases"]),
        ),
        direction=str(record["direction"]),
        document_id=str(record["document_id"]),
        evidence=str(record["evidence"]),
        backend=backend,
    )


def _build_alias_index(entities: list[Entity]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for entity in entities:
        aliases[_normalize_name(entity.name)] = entity.id
        aliases[_normalize_name(entity.id.split(":", 1)[-1])] = entity.id
        for alias in entity.aliases:
            aliases[_normalize_name(alias)] = entity.id
    return aliases


def _graph_entity(entity: Entity) -> GraphEntity:
    return GraphEntity(
        id=entity.id,
        name=entity.name,
        type=entity.type.value,
        aliases=entity.aliases,
    )


def _normalize_name(value: str) -> str:
    return value.strip().lower().replace("“", "").replace("”", "").replace('"', "")


def _resolve_canonical_id(entity_id: str, canonical_id_map: dict[str, str]) -> str:
    current = entity_id
    visited: set[str] = set()
    while current in canonical_id_map:
        if current in visited:
            raise GraphRetrievalError(f"canonical entity mapping contains a cycle at {current}")
        visited.add(current)
        current = canonical_id_map[current]
    return current
