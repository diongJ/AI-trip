"""HTTP adapter for the React museum experience.

The API intentionally delegates every knowledge operation to ``AppRuntime`` so
the website and Streamlit demo share the same evidence, refusal, and fallback
rules.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from functools import lru_cache
from math import ceil
from pathlib import Path
from threading import Lock
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.runtime import AppRuntime
from src.agent.models import AnswerMode, Audience, ConversationTurn
from src.config import get_settings


ROOT = Path(__file__).resolve().parents[1]


class RequestRateLimiter:
    """Small in-process per-IP limiter for the single-instance public demo."""

    def __init__(self, *, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def retry_after(self, client_id: str, *, now: float | None = None) -> int | None:
        if self.limit == 0:
            return None
        timestamp = time.monotonic() if now is None else now
        with self._lock:
            requests = self._requests[client_id]
            cutoff = timestamp - self.window_seconds
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= self.limit:
                return max(1, ceil(self.window_seconds - (timestamp - requests[0])))
            requests.append(timestamp)
            return None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer_mode: AnswerMode = Field(default=AnswerMode.AUTO, alias="answerMode")
    audience: Audience = Field(default=Audience.ADULT)
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


def _release_version() -> str:
    return (
        os.getenv("RELEASE_SHA")
        or os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("GIT_COMMIT_SHA")
        or "local"
    )


def _client_id(request: Request) -> str:
    """Prefer Railway's forwarded visitor address while retaining local support."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        forwarded_client = forwarded_for.split(",", 1)[0].strip()
        if forwarded_client:
            return forwarded_client
    return request.client.host if request.client else "unknown"


def create_app(
    *,
    runtime_provider: Any = get_runtime,
    rate_limit_per_minute: int | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="南越数字博物志 API", version="0.1.0")
    limiter = RequestRateLimiter(
        limit=get_settings().demo_rate_limit_per_minute
        if rate_limit_per_minute is None
        else rate_limit_per_minute
    )
    website_dir = static_dir or ROOT / "website" / "dist"
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
            "rag_ready": getattr(runtime.status, "rag_ready", False),
            "graph_ready": runtime.status.graph_ready,
            "semantic_ready": getattr(runtime.status, "semantic_ready", False),
            "deepseek_configured": runtime.status.deepseek_configured,
            "web_search_configured": getattr(runtime.status, "web_search_configured", False),
            "neo4j_configured": getattr(runtime.status, "neo4j_configured", False),
            "fallback_mode": not runtime.status.deepseek_configured,
            "release": _release_version(),
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
    def ask(request: AskRequest, http_request: Request) -> dict[str, Any]:
        retry_after = limiter.retry_after(_client_id(http_request))
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="提问过于频繁，请稍后再试。",
                headers={"Retry-After": str(retry_after)},
            )
        try:
            outcome = runtime_provider().ask(
                request.question,
                history=request.history,
                answer_mode=request.answer_mode,
                prefer_llm=request.prefer_llm,
                audience=request.audience,
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

    @app.get("/{requested_path:path}", include_in_schema=False)
    def website(requested_path: str) -> FileResponse:
        """Serve the built React app and keep client-side routes refreshable."""
        if requested_path.startswith("api/") or not website_dir.is_dir():
            raise HTTPException(status_code=404, detail="Not found")
        root = website_dir.resolve()
        candidate = (root / requested_path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        index = root / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Website build is unavailable")

    return app


app = create_app()
