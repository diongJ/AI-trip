from datetime import date
from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


class EntityType(StrEnum):
    PERSON = "Person"
    TOMB = "Tomb"
    TOMB_CHAMBER = "TombChamber"
    RELIC = "Relic"
    RELIC_CATEGORY = "RelicCategory"
    MATERIAL = "Material"
    DYNASTY = "Dynasty"
    STATE = "State"
    HISTORICAL_EVENT = "HistoricalEvent"
    CULTURE = "Culture"
    PATTERN = "Pattern"
    EXHIBITION = "Exhibition"


class RelationType(StrEnum):
    BELONGS_TO_STATE = "BELONGS_TO_STATE"
    BURIED_IN = "BURIED_IN"
    CONTAINS = "CONTAINS"
    EXCAVATED_FROM = "EXCAVATED_FROM"
    MADE_OF = "MADE_OF"
    BELONGS_TO_CATEGORY = "BELONGS_TO_CATEGORY"
    CREATED_IN = "CREATED_IN"
    RELATED_TO_PERSON = "RELATED_TO_PERSON"
    REFLECTS_CULTURE = "REFLECTS_CULTURE"
    HAS_PATTERN = "HAS_PATTERN"
    INVOLVES_PERSON = "INVOLVES_PERSON"
    OCCURRED_IN = "OCCURRED_IN"


ALLOWED_RELATION_ENDPOINTS: dict[RelationType, tuple[EntityType, EntityType]] = {
    RelationType.BELONGS_TO_STATE: (EntityType.PERSON, EntityType.STATE),
    RelationType.BURIED_IN: (EntityType.PERSON, EntityType.TOMB),
    RelationType.CONTAINS: (EntityType.TOMB, EntityType.TOMB_CHAMBER),
    RelationType.EXCAVATED_FROM: (EntityType.RELIC, EntityType.TOMB_CHAMBER),
    RelationType.MADE_OF: (EntityType.RELIC, EntityType.MATERIAL),
    RelationType.BELONGS_TO_CATEGORY: (EntityType.RELIC, EntityType.RELIC_CATEGORY),
    RelationType.CREATED_IN: (EntityType.RELIC, EntityType.DYNASTY),
    RelationType.RELATED_TO_PERSON: (EntityType.RELIC, EntityType.PERSON),
    RelationType.REFLECTS_CULTURE: (EntityType.RELIC, EntityType.CULTURE),
    RelationType.HAS_PATTERN: (EntityType.RELIC, EntityType.PATTERN),
    RelationType.INVOLVES_PERSON: (EntityType.HISTORICAL_EVENT, EntityType.PERSON),
    RelationType.OCCURRED_IN: (EntityType.HISTORICAL_EVENT, EntityType.DYNASTY),
}


class Entity(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    type: EntityType
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    source_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @field_validator("aliases", "source_ids")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            stripped = value.strip()
            if stripped and stripped not in normalized:
                normalized.append(stripped)
        return normalized

    @model_validator(mode="after")
    def aliases_must_not_repeat_name(self) -> "Entity":
        self.aliases = [alias for alias in self.aliases if alias != self.name]
        if not self.source_ids:
            raise ValueError("source_ids must contain at least one non-empty document id")
        return self


class Relation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_id: str = Field(min_length=1)
    relation: RelationType
    target_id: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def no_self_relation(self) -> "Relation":
        if self.source_id == self.target_id:
            raise ValueError("self-relations are not allowed in Schema V1")
        return self


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entity_references_and_directions(self) -> "ExtractionResult":
        entities_by_id: dict[str, Entity] = {}
        for entity in self.entities:
            if entity.id in entities_by_id:
                raise ValueError(f"duplicate entity id: {entity.id}")
            entities_by_id[entity.id] = entity

        for relation in self.relations:
            source = entities_by_id.get(relation.source_id)
            target = entities_by_id.get(relation.target_id)
            if source is None or target is None:
                raise ValueError(
                    f"relation {relation.relation} references an entity missing from this extraction"
                )
            expected = ALLOWED_RELATION_ENDPOINTS[relation.relation]
            actual = (source.type, target.type)
            if actual != expected:
                raise ValueError(
                    f"invalid direction for {relation.relation}: "
                    f"expected {expected[0]} -> {expected[1]}, got {actual[0]} -> {actual[1]}"
                )
        return self


class SourceType(StrEnum):
    OFFICIAL = "official"
    ACADEMIC = "academic"
    BOOK = "book"
    MUSEUM = "museum"
    OTHER = "other"


class DocumentCategory(StrEnum):
    MUSEUM = "museum"
    TOMB = "tomb"
    PERSON = "person"
    RELIC = "relic"
    HISTORY = "history"
    CULTURE = "culture"
    EXHIBITION = "exhibition"
    TOURISM = "tourism"


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    doc_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_url: AnyHttpUrl
    source_type: SourceType
    category: DocumentCategory
    retrieved_at: date
    text: str = Field(min_length=1)

