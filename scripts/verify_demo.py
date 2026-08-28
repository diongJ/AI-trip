from __future__ import annotations

from app.runtime import AppRuntime, build_explanation_prompt
from src.config.settings import Settings


def main() -> None:
    runtime = AppRuntime(
        settings=Settings(
            _env_file=None,
            deepseek_api_key=None,
            neo4j_uri=None,
            neo4j_username=None,
            neo4j_password=None,
        )
    )
    checks = [
        _home_path(runtime),
        _question_path(runtime, "文帝行玺是什么材料？", "search_kg"),
        _question_path(
            runtime,
            "丝缕玉衣反映了什么丧葬观念？",
            "hybrid_search",
        ),
        _explanation_path(runtime),
        _graph_path(runtime),
    ]
    passed = sum(checks)
    print(f"Day 6 demo paths: {passed}/{len(checks)} passed")
    if passed != len(checks):
        raise SystemExit("Day 6 demo verification failed")


def _home_path(runtime: AppRuntime) -> bool:
    status = runtime.status
    return (
        status.document_count == 220
        and status.entity_count == 78
        and status.relation_count == 87
    )


def _question_path(runtime: AppRuntime, question: str, expected_tool: str) -> bool:
    outcome = runtime.ask(question, prefer_llm=False)
    return (
        not outcome.response.insufficient_evidence
        and bool(outcome.response.citations)
        and [tool.value for tool in outcome.response.used_tools] == [expected_tool]
    )


def _explanation_path(runtime: AppRuntime) -> bool:
    outcome = runtime.ask(
        build_explanation_prompt("文帝行玺", "简短导览"),
        prefer_llm=False,
    )
    return (
        not outcome.response.insufficient_evidence
        and bool(outcome.response.citations)
        and [tool.value for tool in outcome.response.used_tools] == ["hybrid_search"]
    )


def _graph_path(runtime: AppRuntime) -> bool:
    matches = runtime.list_entities("南越文王", entity_type="Person")
    if not matches or matches[0].name != "赵眜":
        return False
    hits = runtime.neighbors(matches[0].name)
    return bool(hits) and all(hit.document_id and hit.evidence for hit in hits)


if __name__ == "__main__":
    main()
