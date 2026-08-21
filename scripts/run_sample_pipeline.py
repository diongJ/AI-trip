import json
import sys
from pathlib import Path

from neo4j.exceptions import Neo4jError

from src.config import get_settings
from src.config.settings import ConfigurationError
from src.extraction.deepseek import DeepSeekError, DeepSeekExtractor
from src.graph import Neo4jKnowledgeGraph


SAMPLE_IDS = [
    "person:赵眜",
    "tomb:南越文王墓",
    "tombchamber:主棺室",
    "relic:文帝行玺",
]


def main() -> None:
    settings = get_settings()
    sample_text = Path("data/raw/sample_nanyue.txt").read_text(encoding="utf-8")

    print("1/3 Extracting structured knowledge with DeepSeek...")
    with DeepSeekExtractor(settings) as extractor:
        result = extractor.extract(sample_text, "DOC_SAMPLE_001")

    output_path = Path("data/graph/sample_extraction.json")
    output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"2/3 Validated {len(result.entities)} entities and {len(result.relations)} relations")

    with Neo4jKnowledgeGraph(settings) as graph:
        graph.verify_connectivity()
        graph.upsert_extraction(result)
        paths = graph.fetch_paths(SAMPLE_IDS)

    print("3/3 Neo4j paths:")
    print(json.dumps(paths, ensure_ascii=False, indent=2))
    print(f"Validated extraction saved to {output_path}")


if __name__ == "__main__":
    try:
        main()
    except (ConfigurationError, DeepSeekError, Neo4jError) as exc:
        print(f"Sample pipeline failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
