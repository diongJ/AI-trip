from __future__ import annotations

import json

from src.extraction.audit import audit_extractions


def main() -> None:
    report = audit_extractions()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["missing_outputs"] or report["unexpected_outputs"] or report["issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
