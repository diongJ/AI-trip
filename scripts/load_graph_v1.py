from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from neo4j.exceptions import Neo4jError

from src.config import get_settings
from src.config.settings import ConfigurationError
from src.extraction.models import ExtractionResult
from src.graph import Neo4jKnowledgeGraph


CORE_IDS = [
    "person:赵眜",
    "tomb:南越文王墓",
    "relic:文帝行玺",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load and verify knowledge graph V1 in Neo4j Aura.")
    parser.add_argument("--input", default="data/graph/knowledge_graph_v1.json")
    parser.add_argument("--report", default="data/processed/graph_v1_load_report.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = ExtractionResult.model_validate_json(
        Path(args.input).read_text(encoding="utf-8")
    )
    settings = get_settings()
    with Neo4jKnowledgeGraph(settings) as graph:
        graph.verify_connectivity()
        before = graph.get_counts()
        graph.upsert_extraction(result)
        after_first = graph.get_counts()
        first_verification = graph.verify_extraction(result)
        graph.upsert_extraction(result)
        after_second = graph.get_counts()
        second_verification = graph.verify_extraction(result)
        core_paths = graph.fetch_paths(CORE_IDS)

    idempotent = after_first == after_second
    report = {
        "input_file": args.input,
        "expected_entities": len(result.entities),
        "expected_relations": len(result.relations),
        "counts_before": before,
        "counts_after_first_write": after_first,
        "counts_after_second_write": after_second,
        "first_verification": first_verification,
        "second_verification": second_verification,
        "idempotent": idempotent,
        "core_paths": core_paths,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if (
        not idempotent
        or first_verification["missing_entities"]
        or first_verification["missing_relations"]
        or second_verification["missing_entities"]
        or second_verification["missing_relations"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except (ConfigurationError, Neo4jError, OSError, ValueError) as exc:
        print(f"Graph V1 load failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
