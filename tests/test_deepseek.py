import json

import httpx
import pytest

from src.config.settings import Settings
from src.extraction.deepseek import DeepSeekError, DeepSeekExtractor


VALID_RESULT = {
    "entities": [
        {
            "id": "person:赵眜",
            "name": "赵眜",
            "type": "Person",
            "aliases": ["南越文王"],
            "description": "南越国第二代王",
            "source_ids": ["DOC_SAMPLE_001"],
            "confidence": 0.99,
        },
        {
            "id": "tomb:南越文王墓",
            "name": "南越文王墓",
            "type": "Tomb",
            "aliases": [],
            "description": "赵眜的墓葬",
            "source_ids": ["DOC_SAMPLE_001"],
            "confidence": 0.99,
        },
    ],
    "relations": [
        {
            "source_id": "person:赵眜",
            "relation": "BURIED_IN",
            "target_id": "tomb:南越文王墓",
            "evidence": "南越文王墓是南越国第二代王赵眜的墓葬。",
            "document_id": "DOC_SAMPLE_001",
            "confidence": 0.99,
        }
    ],
}


def settings() -> Settings:
    return Settings(_env_file=None, deepseek_api_key="test-secret")


def test_extract_parses_and_validates_json(tmp_path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Return JSON.", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-secret"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(VALID_RESULT)}}]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        extractor = DeepSeekExtractor(settings(), prompt_path=prompt, http_client=client)
        result = extractor.extract("测试文本", "DOC_SAMPLE_001")

    assert result.entities[0].name == "赵眜"
    assert result.relations[0].relation == "BURIED_IN"


def test_extract_rejects_invalid_model_output(tmp_path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Return JSON.", encoding="utf-8")

    def handler(_: httpx.Request) -> httpx.Response:
        invalid = {"entities": [{**VALID_RESULT["entities"][0], "type": "Unknown"}], "relations": []}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(invalid)}}]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        extractor = DeepSeekExtractor(settings(), prompt_path=prompt, http_client=client)
        with pytest.raises(DeepSeekError, match="Schema V1"):
            extractor.extract("测试文本", "DOC_SAMPLE_001")


def test_extract_repairs_schema_invalid_output_once(tmp_path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Return JSON.", encoding="utf-8")
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        body = json.loads(request.content)
        if calls == 1:
            invalid = {
                "entities": VALID_RESULT["entities"],
                "relations": [
                    {
                        **VALID_RESULT["relations"][0],
                        "source_id": "tomb:南越文王墓",
                        "target_id": "person:赵眜",
                    }
                ],
            }
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": json.dumps(invalid)}}]},
            )
        assert "未通过 Schema V1 校验" in body["messages"][-1]["content"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(VALID_RESULT)}}]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        extractor = DeepSeekExtractor(settings(), prompt_path=prompt, http_client=client)
        result = extractor.extract("测试文本", "DOC_SAMPLE_001")

    assert calls == 2
    assert result.relations[0].source_id == "person:赵眜"


def test_extract_drops_invalid_relation_after_failed_repair(tmp_path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Return JSON.", encoding="utf-8")
    invalid = {
        "entities": VALID_RESULT["entities"],
        "relations": [
            {
                **VALID_RESULT["relations"][0],
                "source_id": "tomb:南越文王墓",
                "target_id": "person:赵眜",
            }
        ],
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(invalid)}}]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        extractor = DeepSeekExtractor(settings(), prompt_path=prompt, http_client=client)
        result = extractor.extract("测试文本", "DOC_SAMPLE_001")

    assert len(result.entities) == 2
    assert result.relations == []


def test_extractor_rejects_negative_schema_repair_count(tmp_path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Return JSON.", encoding="utf-8")

    with pytest.raises(ValueError, match="schema_repair_attempts"):
        DeepSeekExtractor(settings(), prompt_path=prompt, schema_repair_attempts=-1)
