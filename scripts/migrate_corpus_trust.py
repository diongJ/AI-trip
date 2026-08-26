from __future__ import annotations

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse


NORMALIZE_RE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff]+")


def _normalized(text: str) -> str:
    return NORMALIZE_RE.sub("", text).lower()


def _shingles(text: str, size: int = 3) -> set[str]:
    normalized = _normalized(text)
    if len(normalized) <= size:
        return {normalized} if normalized else set()
    return {normalized[index : index + size] for index in range(len(normalized) - size + 1)}


def _overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _role(payload: dict) -> str:
    if payload.get("source_type") == "other" or payload.get("source_name") == "AI-trip 项目整理":
        return "curated_guidance"
    return "factual"


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移并审计语料可信度元数据。")
    parser.add_argument("--root", default="data/raw")
    parser.add_argument("--config", default="config/trusted_sources.json")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    allowed_domains = {
        domain.lower()
        for source in config.get("sources", [])
        for domain in source.get("domains", [])
    }
    files = sorted(root.rglob("*.json"))
    documents: list[tuple[Path, dict]] = []
    changed = 0
    issues: list[dict[str, object]] = []

    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        role = _role(payload)
        review_status = payload.get("review_status") or "approved"
        content_hash = sha256(str(payload["text"]).encode("utf-8")).hexdigest()
        updates = {
            "evidence_role": role,
            "content_hash": content_hash,
            "review_status": review_status,
        }
        if any(payload.get(key) != value for key, value in updates.items()):
            payload.update(updates)
            changed += 1
            if args.apply:
                path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

        domain = (urlparse(str(payload.get("source_url", ""))).hostname or "").lower()
        if role == "curated_guidance":
            if payload.get("category") != "tourism" or payload.get("source_type") != "other":
                issues.append({"doc_id": payload.get("doc_id"), "issue": "invalid_curated_guidance"})
        elif payload.get("source_tier") == "extended" and domain not in allowed_domains:
            issues.append(
                {"doc_id": payload.get("doc_id"), "issue": "extended_source_not_whitelisted", "domain": domain}
            )
        documents.append((path, payload))

    exact: dict[str, list[str]] = {}
    for _path, payload in documents:
        exact.setdefault(_normalized(str(payload["text"])), []).append(str(payload["doc_id"]))
    for ids in exact.values():
        if len(ids) > 1:
            issues.append({"issue": "normalized_duplicate", "doc_ids": ids})

    shingles = {str(payload["doc_id"]): _shingles(str(payload["text"])) for _path, payload in documents}
    by_id = {str(payload["doc_id"]): payload for _path, payload in documents}
    ids = sorted(shingles)
    near_duplicates: list[dict[str, object]] = []
    for left_index, left_id in enumerate(ids):
        for right_id in ids[left_index + 1 :]:
            left = by_id[left_id]
            right = by_id[right_id]
            same_source = str(left.get("source_url")) == str(right.get("source_url"))
            both_curated = left.get("evidence_role") == right.get("evidence_role") == "curated_guidance"
            if not (same_source or both_curated):
                continue
            score = _overlap(shingles[left_id], shingles[right_id])
            if score >= 0.9:
                near_duplicates.append(
                    {"doc_ids": [left_id, right_id], "shingle_jaccard": round(score, 4)}
                )
    if near_duplicates:
        issues.extend({"issue": "near_duplicate", **item} for item in near_duplicates)

    report = {
        "documents": len(documents),
        "changed": changed,
        "applied": args.apply,
        "factual": sum(payload["evidence_role"] == "factual" for _path, payload in documents),
        "curated_guidance": sum(
            payload["evidence_role"] == "curated_guidance" for _path, payload in documents
        ),
        "issues": issues,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
