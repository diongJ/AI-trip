from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.preprocessing import CorpusDocument
from src.preprocessing.sources import (
    SourceConfig,
    _clean_page_text,
    _clean_title,
    _is_relevant,
    _topic_tags,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="清洗扩展语料并隔离无实质正文的页面。")
    parser.add_argument("--root", default="data/raw/extended")
    parser.add_argument("--config", default="config/trusted_sources.json")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore-eligible", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    config = SourceConfig.from_path(args.config)
    defaults = ["南越专题"]
    report = {"checked": 0, "kept": 0, "quarantined": 0, "changed": 0, "items": []}
    for path in sorted(root.rglob("*.json")):
        document = CorpusDocument.model_validate_json(path.read_text(encoding="utf-8"))
        report["checked"] += 1
        cleaned = _clean_page_text(document.text, document.title)
        is_collection = (
            document.source_name == "南越王博物院"
            and "/Collection/Details/" in str(document.source_url)
        )
        relevant = is_collection or _is_relevant(cleaned, config.relevance_keywords)
        minimum = 70 if document.category in {"relic", "exhibition"} or is_collection else 180
        if len(cleaned) < minimum or not relevant:
            report["quarantined"] += 1
            report["items"].append({"doc_id": document.doc_id, "action": "quarantine", "chars": len(cleaned)})
            if args.apply:
                target = Path("data/quarantine/extended") / path.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                path.replace(target)
            continue
        updated = document.model_copy(
            update={
                "title": _clean_title(document.title, str(document.source_url), cleaned),
                "text": cleaned,
                "content_hash": "",
                "topic_tags": _topic_tags(cleaned, defaults),
                "version": document.version + 1,
            }
        )
        updated = CorpusDocument.model_validate(updated.model_dump())
        report["kept"] += 1
        if updated.text != document.text or updated.title != document.title:
            report["changed"] += 1
            if args.apply:
                path.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    if args.restore_eligible:
        quarantine_root = Path("data/quarantine/extended")
        active_ids = {path.stem for path in root.rglob("*.json")}
        for path in sorted(quarantine_root.rglob("*.json")):
            document = CorpusDocument.model_validate_json(path.read_text(encoding="utf-8"))
            if document.doc_id in active_ids:
                continue
            cleaned = _clean_page_text(document.text, document.title)
            is_collection = (
                document.source_name == "南越王博物院"
                and "/Collection/Details/" in str(document.source_url)
            )
            minimum = 70 if document.category in {"relic", "exhibition"} or is_collection else 180
            if len(cleaned) < minimum or not (
                is_collection or _is_relevant(cleaned, config.relevance_keywords)
            ):
                continue
            updated = document.model_copy(
                update={
                    "title": _clean_title(document.title, str(document.source_url), cleaned),
                    "text": cleaned,
                    "content_hash": "",
                    "topic_tags": _topic_tags(cleaned, defaults),
                    "version": document.version + 1,
                }
            )
            updated = CorpusDocument.model_validate(updated.model_dump())
            report["kept"] += 1
            report["changed"] += 1
            report["items"].append({"doc_id": document.doc_id, "action": "restore", "chars": len(cleaned)})
            if args.apply:
                target = root / updated.category / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
                path.unlink()
                active_ids.add(document.doc_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
