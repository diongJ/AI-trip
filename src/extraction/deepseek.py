import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from src.config.settings import Settings
from src.extraction.models import ALLOWED_RELATION_ENDPOINTS, ExtractionResult, Relation


class DeepSeekError(RuntimeError):
    """Raised when the DeepSeek extraction request cannot produce valid knowledge."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class DeepSeekExtractor:
    def __init__(
        self,
        settings: Settings,
        *,
        prompt_path: Path | None = None,
        http_client: httpx.Client | None = None,
        schema_repair_attempts: int = 1,
    ) -> None:
        settings.require_deepseek()
        if schema_repair_attempts < 0:
            raise ValueError("schema_repair_attempts must not be negative")
        self.settings = settings
        self.prompt_path = prompt_path or Path("prompts/knowledge_extraction.txt")
        self._owns_client = http_client is None
        self.client = http_client or httpx.Client(timeout=60.0)
        self.schema_repair_attempts = schema_repair_attempts

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

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"document_id: {document_id}\n\n待抽取文本：\n{text}",
            },
        ]
        last_validation_error: ValidationError | None = None
        last_parsed: object = None
        for repair_attempt in range(self.schema_repair_attempts + 1):
            content = self._request_content(messages)
            try:
                parsed = json.loads(self._strip_code_fence(content))
                last_parsed = parsed
                return ExtractionResult.model_validate(parsed)
            except (TypeError, json.JSONDecodeError) as exc:
                raise DeepSeekError(
                    f"DeepSeek request returned invalid JSON: {exc}"
                ) from exc
            except ValidationError as exc:
                last_validation_error = exc
                if repair_attempt == self.schema_repair_attempts:
                    break
                messages.extend(
                    [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": (
                                "上次 JSON 未通过 Schema V1 校验。只修正 JSON，不要解释；"
                                "删除无法满足关系端点类型的关系。校验错误如下：\n"
                                f"{exc}"
                            ),
                        },
                    ]
                )
        conservative = self._drop_invalid_relations(last_parsed)
        if conservative is not None:
            return conservative
        raise DeepSeekError(
            f"DeepSeek output failed Schema V1 validation: {last_validation_error}"
        )

    @staticmethod
    def _drop_invalid_relations(parsed: object) -> ExtractionResult | None:
        """Keep valid entities and relations when only some model relations are invalid."""
        if not isinstance(parsed, dict) or set(parsed) != {"entities", "relations"}:
            return None
        if not isinstance(parsed["entities"], list) or not isinstance(
            parsed["relations"], list
        ):
            return None
        try:
            entity_only = ExtractionResult.model_validate(
                {"entities": parsed["entities"], "relations": []}
            )
        except ValidationError:
            return None

        entities_by_id = {entity.id: entity for entity in entity_only.entities}
        valid_relations: list[Relation] = []
        for relation_payload in parsed["relations"]:
            try:
                relation = Relation.model_validate(relation_payload)
            except ValidationError:
                continue
            source = entities_by_id.get(relation.source_id)
            target = entities_by_id.get(relation.target_id)
            if source is None or target is None:
                continue
            if (source.type, target.type) != ALLOWED_RELATION_ENDPOINTS[
                relation.relation
            ]:
                continue
            valid_relations.append(relation)
        return ExtractionResult(entities=entity_only.entities, relations=valid_relations)

    def _request_content(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.settings.deepseek_model,
            "messages": messages,
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
            if not isinstance(content, str):
                raise TypeError("message content must be a string")
            return content
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise DeepSeekError(
                f"DeepSeek request failed with HTTP {status}",
                retryable=status == 429 or status >= 500,
            ) from exc
        except httpx.TransportError as exc:
            raise DeepSeekError(
                f"DeepSeek request failed before receiving a response: {exc}",
                retryable=True,
            ) from exc
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise DeepSeekError(f"DeepSeek request returned an unusable response: {exc}") from exc

    @staticmethod
    def _strip_code_fence(content: str) -> str:
        value = content.strip()
        if value.startswith("```"):
            lines = value.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                return "\n".join(lines[1:-1]).strip()
        return value
