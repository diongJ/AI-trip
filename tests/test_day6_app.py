from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from app.bootstrap import require_project_environment
from app.runtime import (
    AppRuntime,
    build_explanation_prompt,
    explanation_markdown,
    safe_download_name,
)
from src.agent.service import AnswerGenerationError
from src.config.settings import Settings


@pytest.fixture(scope="module")
def offline_runtime() -> AppRuntime:
    return AppRuntime(
        settings=Settings(
            _env_file=None,
            deepseek_api_key=None,
            neo4j_uri=None,
            neo4j_username=None,
            neo4j_password=None,
        )
    )


def test_runtime_status_is_ready_and_contains_no_secrets(offline_runtime) -> None:
    assert offline_runtime.status.document_count == 100
    assert offline_runtime.status.entity_count == 78
    assert offline_runtime.status.relation_count == 87
    assert not offline_runtime.status.deepseek_configured
    assert "password" not in repr(offline_runtime.status).lower()
    assert "api_key" not in repr(offline_runtime.status).lower()


def test_wrong_python_environment_shows_actionable_command(monkeypatch) -> None:
    class Stopped(RuntimeError):
        pass

    class FakeStreamlit:
        def __init__(self) -> None:
            self.messages = []

        def error(self, value):
            self.messages.append(value)

        def write(self, value):
            self.messages.append(value)

        def code(self, value, **_):
            self.messages.append(value)

        def caption(self, value):
            self.messages.append(value)

        def stop(self):
            raise Stopped

    monkeypatch.setattr("app.bootstrap.find_spec", lambda name: None)
    fake = FakeStreamlit()

    with pytest.raises(Stopped):
        require_project_environment(fake)

    text = "\n".join(fake.messages)
    assert ".venv\\Scripts\\python.exe -m streamlit" in text
    assert "pydantic" in text


def test_streamlit_hides_external_error_links_and_developer_toolbar() -> None:
    project_root = Path(__file__).resolve().parents[1]
    config = tomllib.loads(
        (project_root / ".streamlit/config.toml").read_text(encoding="utf-8")
    )

    assert config["client"]["showErrorDetails"] == "none"
    assert config["client"]["showErrorLinks"] is False
    assert config["client"]["toolbarMode"] == "minimal"


def test_runtime_falls_back_when_deepseek_fails(offline_runtime) -> None:
    class FailingService:
        def answer(self, question: str):
            raise AnswerGenerationError("simulated network error with sensitive detail")

    original = offline_runtime.deepseek_service
    offline_runtime.deepseek_service = FailingService()
    try:
        outcome = offline_runtime.ask("文帝行玺是什么材料？")
    finally:
        offline_runtime.deepseek_service = original

    assert outcome.generation_mode == "离线证据摘录"
    assert outcome.warning == "智能生成服务暂时不可用，本次已回退到离线证据摘录。"
    assert outcome.response.citations
    assert "sensitive" not in outcome.warning


def test_explanation_prompt_forces_hybrid_and_validates_style(offline_runtime) -> None:
    prompt = build_explanation_prompt("文帝行玺", "亲子版")
    outcome = offline_runtime.ask(prompt, prefer_llm=False)

    assert "文帝行玺" in prompt
    assert "结合文物证据" in prompt
    assert [tool.value for tool in outcome.response.used_tools] == ["hybrid_search"]
    with pytest.raises(ValueError, match="unsupported"):
        build_explanation_prompt("文帝行玺", "未知风格")


def test_explanation_markdown_contains_answer_and_sources(offline_runtime) -> None:
    outcome = offline_runtime.ask(
        build_explanation_prompt("文帝行玺", "简短导览"),
        prefer_llm=False,
    )
    markdown = explanation_markdown("文帝行玺", "简短导览", outcome)

    assert markdown.startswith("# 文帝行玺｜简短导览")
    assert "## 参考来源" in markdown
    assert "DOC_" in markdown
    assert safe_download_name("文帝/行玺", "亲子版") == "文帝_行玺_亲子版.md"


@pytest.mark.parametrize(
    "page",
    [
        "app/Home.py",
        "app/pages/1_智能问答.py",
        "app/pages/2_AI深度讲解.py",
        "app/pages/3_图谱探索.py",
    ],
)
def test_streamlit_pages_render_without_uncaught_exceptions(page) -> None:
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    project_root = Path(__file__).resolve().parents[1]
    app = streamlit_testing.AppTest.from_file(
        project_root / page,
        default_timeout=15,
    ).run()

    assert not app.exception


def test_graph_page_can_follow_a_neighbor_without_errors() -> None:
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    project_root = Path(__file__).resolve().parents[1]
    app = streamlit_testing.AppTest.from_file(
        project_root / "app/pages/3_图谱探索.py",
        default_timeout=15,
    ).run()
    initial_path = list(app.session_state["graph_path"])

    app.button[0].click().run()

    assert not app.exception
    assert len(app.session_state["graph_path"]) == len(initial_path) + 1


def test_question_page_clears_chat_history(offline_runtime) -> None:
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    project_root = Path(__file__).resolve().parents[1]
    app = streamlit_testing.AppTest.from_file(
        project_root / "app/pages/1_智能问答.py",
        default_timeout=15,
    )
    app.session_state["chat_history"] = [
        {
            "question": "文帝行玺是什么材料？",
            "outcome": offline_runtime.ask(
                "文帝行玺是什么材料？",
                prefer_llm=False,
            ),
        }
    ]
    app.run()

    clear_button = next(button for button in app.button if button.label == "清空会话")
    clear_button.click().run()

    assert not app.exception
    assert app.session_state["chat_history"] == []
