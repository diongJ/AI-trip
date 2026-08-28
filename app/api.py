"""HTTP adapter for the React museum experience.

The API intentionally delegates every knowledge operation to ``AppRuntime`` so
the website and Streamlit demo share the same evidence, refusal, and fallback
rules.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.runtime import AppRuntime
from src.agent.models import AnswerMode, ConversationTurn


ROOT = Path(__file__).resolve().parents[1]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer_mode: AnswerMode = Field(default=AnswerMode.AUTO, alias="answerMode")
    history: list[ConversationTurn] = Field(default_factory=list, max_length=6)
    prefer_llm: bool = True


def _origins() -> list[str]:
    raw = os.getenv("NANYUE_WEB_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _load_evaluation() -> dict[str, Any]:
    path = ROOT / "data" / "evaluation" / "summary_v2.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@lru_cache
def get_runtime() -> AppRuntime:
    return AppRuntime()


def _answer_payload(outcome: Any) -> dict[str, Any]:
    response = outcome.response
    return {
        "answer": response.answer,
        "citations": [citation.model_dump(mode="json") for citation in response.citations],
        "web_sources": [source.model_dump(mode="json") for source in response.web_sources],
        "route_reason": response.route_reason,
        "used_tools": [str(tool) for tool in response.used_tools],
        "insufficient_evidence": response.insufficient_evidence,
        "response_status": response.response_status,
        "suggested_questions": response.suggested_questions,
        "generation_mode": outcome.generation_mode,
        "warning": outcome.warning,
        "elapsed_ms": outcome.elapsed_ms,
    }


def _entity_payload(entity: Any) -> dict[str, Any]:
    return {"id": entity.id, "name": entity.name, "type": entity.type, "aliases": entity.aliases}


def _graph_payload(hit: Any) -> dict[str, Any]:
    return {
        "source": _entity_payload(hit.source_entity),
        "relation": hit.relation,
        "target": _entity_payload(hit.target_entity),
        "direction": hit.direction,
        "document_id": hit.document_id,
        "evidence": hit.evidence,
    }


def create_app(*, runtime_provider: Any = get_runtime) -> FastAPI:
    app = FastAPI(title="南越数字博物志 API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        runtime = runtime_provider()
        return {
            "status": "ok",
            "corpus_ready": runtime.status.corpus_ready,
            "graph_ready": runtime.status.graph_ready,
            "deepseek_configured": runtime.status.deepseek_configured,
            "fallback_mode": not runtime.status.deepseek_configured,
        }

    @app.get("/api/stats")
    def stats() -> dict[str, Any]:
        runtime = runtime_provider()
        evaluation = _load_evaluation()
        return {
            "documents": runtime.status.document_count,
            "entities": runtime.status.entity_count,
            "relations": runtime.status.relation_count,
            "evaluation": evaluation,
        }

    @app.post("/api/ask")
    def ask(request: AskRequest) -> dict[str, Any]:
        try:
            outcome = runtime_provider().ask(
                request.question,
                history=request.history,
                answer_mode=request.answer_mode,
                prefer_llm=request.prefer_llm,
            )
        except Exception as exc:  # Avoid exposing settings, paths, or provider details to visitors.
            raise HTTPException(status_code=503, detail="问答服务暂时不可用，请稍后重试。") from exc
        return _answer_payload(outcome)

    @app.get("/api/entities")
    def entities(
        q: str = "",
        entity_type: Annotated[str | None, Query(alias="type")] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 24,
    ) -> dict[str, Any]:
        rows = runtime_provider().list_entities(q, entity_type=entity_type, limit=limit)
        return {"entities": [_entity_payload(entity) for entity in rows]}

    @app.get("/api/entities/{entity_name}/neighbors")
    def neighbors(entity_name: str, limit: Annotated[int, Query(ge=1, le=30)] = 12) -> dict[str, Any]:
        runtime = runtime_provider()
        matches = runtime.list_entities(entity_name, limit=1)
        if not matches:
            raise HTTPException(status_code=404, detail="未找到该实体。")
        entity = matches[0]
        return {
            "entity": _entity_payload(entity),
            "neighbors": [_graph_payload(hit) for hit in runtime.neighbors(entity.name, limit=limit)],
        }

    return app


app = create_app()
