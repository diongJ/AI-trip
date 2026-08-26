from __future__ import annotations

import argparse
import json
from pathlib import Path

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
    summary = build_graph_v1(
        input_dir=args.input_dir,
        raw_dir=args.raw_dir,
        resolution=args.resolution,
        output=args.output,
        report_path=args.report,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def build_graph_v1(
    *,
    input_dir: str | Path = "data/graph/by_document",
    raw_dir: str | Path = "data/raw",
    resolution: str | Path = "data/curated/entity_resolution_v1.json",
    output: str | Path = "data/graph/knowledge_graph_v1.json",
    report_path: str | Path = "data/processed/graph_v1_fusion_report.json",
) -> dict[str, object]:
    result, fusion_report = fuse_extractions(
        input_dir, resolution, raw_dir=raw_dir
    )
    write_graph_v1(result, fusion_report, output, report_path)
    summary: dict[str, object] = fusion_report.model_dump(mode="json")
    summary["output_file"] = str(output)
    summary["report_file"] = str(report_path)
    return summary


if __name__ == "__main__":
    main()
