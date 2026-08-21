import sys
from pathlib import Path

from src.config import get_settings
from src.config.settings import ConfigurationError
from src.extraction.deepseek import DeepSeekError, DeepSeekExtractor


def main() -> None:
    text = Path("data/raw/sample_nanyue.txt").read_text(encoding="utf-8")
    with DeepSeekExtractor(get_settings()) as extractor:
        result = extractor.extract(text, "DOC_SAMPLE_001")
    print(result.model_dump_json(indent=2))
    print(f"DeepSeek validation passed: {len(result.entities)} entities, "
          f"{len(result.relations)} relations")


if __name__ == "__main__":
    try:
        main()
    except (ConfigurationError, DeepSeekError) as exc:
        print(f"DeepSeek validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
