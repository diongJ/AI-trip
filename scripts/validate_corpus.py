from __future__ import annotations

import json
from collections import Counter

from src.preprocessing import load_corpus


def main() -> None:
    documents = load_corpus("data/raw")
    categories = Counter(document.category for document in documents)
    print(
        json.dumps(
            {
                "documents": len(documents),
                "categories": dict(sorted(categories.items())),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
