from __future__ import annotations

import argparse
import json

from src.rag.index import build_rag_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the local RAG retrieval index.")
    parser.add_argument("--force", action="store_true", help="rebuild even when a manifest exists")
    parser.add_argument("--chunk-size", type=int, default=420)
    parser.add_argument("--chunk-overlap", type=int, default=60)
    args = parser.parse_args()

    manifest = build_rag_index(
        force=args.force,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
