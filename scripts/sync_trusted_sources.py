from __future__ import annotations

import argparse

from src.preprocessing.sources import sync_sources


def main() -> None:
    parser = argparse.ArgumentParser(description="同步白名单南越专题资料并增量写入语料库。")
    parser.add_argument("--config", default="config/trusted_sources.json")
    parser.add_argument("--max-pages", type=int, default=250)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = sync_sources(
        args.config,
        max_pages=args.max_pages,
        dry_run=args.dry_run,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
