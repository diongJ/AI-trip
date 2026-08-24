from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Protocol

from src.extraction.deepseek import DeepSeekError
from src.extraction.models import Entity, ExtractionResult, Relation, RelationType
from src.preprocessing import CorpusDocument


class KnowledgeExtractor(Protocol):
    def extract(self, text: str, document_id: str) -> ExtractionResult: ...


@dataclass(frozen=True)
class BatchItemResult:
    input_file: str
    doc_id: str | None
    status: Literal["succeeded", "failed", "skipped"]
    entities: int = 0
    relations: int = 0
    output_file: str | None = None
    error_stage: Literal["input", "extraction", "output"] | None = None
    error: str | None = None
    attempts: int = 0
    dropped_relations: int = 0
    cleared_descriptions: int = 0
    dropped_aliases: int = 0


@dataclass(frozen=True)
class BatchReport:
    items: list[BatchItemResult]

    def to_dict(self) -> dict[str, object]:
        return {
            "total": len(self.items),
            "succeeded": sum(item.status == "succeeded" for item in self.items),
            "failed": sum(item.status == "failed" for item in self.items),
            "skipped": sum(item.status == "skipped" for item in self.items),
            "entities": sum(item.entities for item in self.items),
            "relations": sum(item.relations for item in self.items),
            "dropped_relations": sum(item.dropped_relations for item in self.items),
            "cleared_descriptions": sum(
                item.cleared_descriptions for item in self.items
            ),
            "dropped_aliases": sum(item.dropped_aliases for item in self.items),
            "items": [asdict(item) for item in self.items],
        }

    @property
    def failed(self) -> int:
        return sum(item.status == "failed" for item in self.items)


class BatchExtractionRunner:
    def __init__(
        self,
        extractor: KnowledgeExtractor,
        *,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must not be negative")
        self.extractor = extractor
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds

    def run(
        self,
        input_dir: str | Path,
        output_dir: str | Path,
        *,
        force: bool = False,
    ) -> BatchReport:
        input_root = Path(input_dir)
        output_root = Path(output_dir)
        if not input_root.is_dir():
            raise FileNotFoundError(f"input directory does not exist: {input_root}")
        output_root.mkdir(parents=True, exist_ok=True)
        items: list[BatchItemResult] = []
        seen_ids: set[str] = set()

        for path in sorted(input_root.rglob("*.json")):
            payload: object = None
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                document = CorpusDocument.model_validate(payload)
            except Exception as exc:  # noqa: BLE001 - report every invalid input
                items.append(
                    BatchItemResult(
                        input_file=str(path),
                        doc_id=self._candidate_doc_id(payload),
                        status="failed",
                        error_stage="input",
                        error=str(exc),
                    )
                )
                continue

            if document.doc_id in seen_ids:
                items.append(
                    BatchItemResult(
                        input_file=str(path),
                        doc_id=document.doc_id,
                        status="failed",
                        error_stage="input",
                        error=f"duplicate doc_id {document.doc_id}",
                    )
                )
                continue
            seen_ids.add(document.doc_id)

            output_path = output_root / f"{document.doc_id}.json"
            if output_path.exists() and not force:
                existing = self._load_existing(output_path)
                if existing is not None:
                    existing, dropped, cleared, aliases_dropped = self._sanitize_result(
                        existing, document
                    )
                    if dropped or cleared or aliases_dropped:
                        self._write_result(output_path, existing)
                    items.append(
                        self._completed_item(
                            path,
                            document.doc_id,
                            output_path,
                            existing,
                            "skipped",
                            0,
                            dropped,
                            cleared,
                            aliases_dropped,
                        )
                    )
                    continue

            try:
                result, attempts = self._extract_with_retry(document)
            except DeepSeekError as exc:
                items.append(
                    BatchItemResult(
                        input_file=str(path),
                        doc_id=document.doc_id,
                        status="failed",
                        error_stage="extraction",
                        error=str(exc),
                        attempts=getattr(exc, "attempts", self.max_attempts),
                    )
                )
                continue

            result, dropped, cleared, aliases_dropped = self._sanitize_result(
                result, document
            )
            try:
                self._write_result(output_path, result)
            except OSError as exc:
                items.append(
                    BatchItemResult(
                        input_file=str(path),
                        doc_id=document.doc_id,
                        status="failed",
                        error_stage="output",
                        error=str(exc),
                        attempts=attempts,
                    )
                )
                continue

            items.append(
                self._completed_item(
                    path,
                    document.doc_id,
                    output_path,
                    result,
                    "succeeded",
                    attempts,
                    dropped,
                    cleared,
                    aliases_dropped,
                )
            )

        return BatchReport(items)

    def _extract_with_retry(
        self, document: CorpusDocument
    ) -> tuple[ExtractionResult, int]:
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self.extractor.extract(document.text, document.doc_id), attempt
            except DeepSeekError as exc:
                if not exc.retryable or attempt == self.max_attempts:
                    exc.attempts = attempt
                    raise
                if self.retry_delay_seconds:
                    time.sleep(self.retry_delay_seconds * attempt)
        raise AssertionError("retry loop exited unexpectedly")

    @staticmethod
    def _load_existing(path: Path) -> ExtractionResult | None:
        try:
            return ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - an invalid generated file must be regenerated
            return None

    @staticmethod
    def _write_result(path: Path, result: ExtractionResult) -> None:
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _sanitize_result(
        result: ExtractionResult, document: CorpusDocument
    ) -> tuple[ExtractionResult, int, int, int]:
        entities: list[Entity] = []
        cleared_descriptions = 0
        dropped_aliases = 0
        for entity in result.entities:
            aliases = [alias for alias in entity.aliases if alias in document.text]
            dropped_aliases += len(entity.aliases) - len(aliases)
            description = entity.description
            if description and description not in document.text:
                description = ""
                cleared_descriptions += 1
            entities.append(
                entity.model_copy(
                    update={"aliases": aliases, "description": description}
                )
            )
        entities_by_id = {entity.id: entity for entity in entities}
        relations = [
            relation
            for relation in result.relations
            if relation.document_id == document.doc_id
            and relation.evidence in document.text
            and BatchExtractionRunner._has_required_evidence_anchors(
                relation, entities_by_id
            )
        ]
        dropped = len(result.relations) - len(relations)
        sanitized = result.model_copy(
            update={"entities": entities, "relations": relations}
        )
        return sanitized, dropped, cleared_descriptions, dropped_aliases

    @staticmethod
    def _has_required_evidence_anchors(
        relation: Relation, entities_by_id: dict[str, Entity]
    ) -> bool:
        source = entities_by_id[relation.source_id]
        target = entities_by_id[relation.target_id]

        def mentioned(entity: Entity) -> bool:
            return any(
                name and name in relation.evidence
                for name in (entity.name, *entity.aliases)
            )

        require_source = {
            RelationType.BELONGS_TO_STATE,
            RelationType.BURIED_IN,
        }
        require_target = {
            RelationType.CONTAINS,
            RelationType.EXCAVATED_FROM,
            RelationType.MADE_OF,
            RelationType.CREATED_IN,
            RelationType.RELATED_TO_PERSON,
            RelationType.INVOLVES_PERSON,
            RelationType.OCCURRED_IN,
        }
        return not (
            relation.relation in require_source
            and not mentioned(source)
            or relation.relation in require_target
            and not mentioned(target)
        )

    @staticmethod
    def _candidate_doc_id(payload: object) -> str | None:
        if isinstance(payload, dict) and isinstance(payload.get("doc_id"), str):
            return payload["doc_id"]
        return None

    @staticmethod
    def _completed_item(
        input_path: Path,
        doc_id: str,
        output_path: Path,
        result: ExtractionResult,
        status: Literal["succeeded", "skipped"],
        attempts: int,
        dropped_relations: int,
        cleared_descriptions: int,
        dropped_aliases: int,
    ) -> BatchItemResult:
        return BatchItemResult(
            input_file=str(input_path),
            doc_id=doc_id,
            status=status,
            entities=len(result.entities),
            relations=len(result.relations),
            output_file=str(output_path),
            attempts=attempts,
            dropped_relations=dropped_relations,
            cleared_descriptions=cleared_descriptions,
            dropped_aliases=dropped_aliases,
        )
