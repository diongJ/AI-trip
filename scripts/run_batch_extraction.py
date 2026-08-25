from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import get_settings
from src.extraction.batch import BatchExtractionRunner
from src.extraction.deepseek import DeepSeekExtractor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract the raw corpus document by document.")
    parser.add_argument("--input-dir", default="data/raw")
    parser.add_argument("--output-dir", default="data/graph/by_document")
    parser.add_argument(
        "--report-path", default="data/processed/batch_extraction_report.json"
    )
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    with DeepSeekExtractor(settings) as extractor:
        report = BatchExtractionRunner(
            extractor, max_attempts=args.max_attempts
        ).run(args.input_dir, args.output_dir, force=args.force)

    report_data = report.to_dict()
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report_data, ensure_ascii=False, indent=2))
    if report.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
