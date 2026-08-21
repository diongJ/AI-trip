import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from src.config.settings import Settings
from src.extraction.models import ExtractionResult


class DeepSeekError(RuntimeError):
    """Raised when the DeepSeek extraction request cannot produce valid knowledge."""


class DeepSeekExtractor:
    def __init__(
        self,
        settings: Settings,
        *,
        prompt_path: Path | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        settings.require_deepseek()
        self.settings = settings
        self.prompt_path = prompt_path or Path("prompts/knowledge_extraction.txt")
        self._owns_client = http_client is None
        self.client = http_client or httpx.Client(timeout=60.0)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "DeepSeekExtractor":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def extract(self, text: str, document_id: str) -> ExtractionResult:
        if not text.strip():
            raise ValueError("text must not be empty")
        if not document_id.strip():
            raise ValueError("document_id must not be empty")
        try:
            system_prompt = self.prompt_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise DeepSeekError(f"Cannot read extraction prompt: {self.prompt_path}") from exc

        payload = {
            "model": self.settings.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"document_id: {document_id}\n\n待抽取文本：\n{text}",
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        url = f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions"
        try:
            response = self.client.post(
                url,
                headers={
                    "Authorization": (
                        f"Bearer {self.settings.deepseek_api_key.get_secret_value()}"
                    ),
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(self._strip_code_fence(content))
            return ExtractionResult.model_validate(parsed)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise DeepSeekError(f"DeepSeek request returned an unusable response: {exc}") from exc
        except ValidationError as exc:
            raise DeepSeekError(f"DeepSeek output failed Schema V1 validation: {exc}") from exc

    @staticmethod
    def _strip_code_fence(content: str) -> str:
        value = content.strip()
        if value.startswith("```"):
            lines = value.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                return "\n".join(lines[1:-1]).strip()
        return value

