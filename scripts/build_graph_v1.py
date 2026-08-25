from __future__ import annotations

import argparse
import json

from src.graph.fusion import fuse_extractions, write_graph_v1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the deterministic knowledge graph V1.")
    parser.add_argument("--input-dir", default="data/graph/by_document")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--resolution", default="data/curated/entity_resolution_v1.json")
    parser.add_argument("--output", default="data/graph/knowledge_graph_v1.json")
    parser.add_argument("--report", default="data/processed/graph_v1_fusion_report.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result, report = fuse_extractions(
        args.input_dir, args.resolution, raw_dir=args.raw_dir
    )
    write_graph_v1(result, report, args.output, args.report)
    summary = report.model_dump(mode="json")
    summary["output_file"] = args.output
    summary["report_file"] = args.report
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
