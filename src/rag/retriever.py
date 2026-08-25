from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from src.rag.index import DEFAULT_INDEX_DIR, LEXICAL_BACKEND, load_chunks, tokenize
from src.rag.models import DocumentChunk, RetrievalHit


class RagIndexError(RuntimeError):
    pass


class RagRetriever:
    def __init__(self, index_dir: str | Path = DEFAULT_INDEX_DIR) -> None:
        self.index_dir = Path(index_dir)
        self.chunks = load_chunks(self.index_dir / "chunks.json")
        index_path = self.index_dir / "lexical_index.json"
        if not index_path.exists():
            raise RagIndexError(
                f"RAG index file is missing: {index_path}. Run python -m scripts.build_rag_index first."
            )
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        if payload.get("backend") != LEXICAL_BACKEND:
            raise RagIndexError(f"unsupported RAG backend: {payload.get('backend')}")
        self.idf: dict[str, float] = payload["idf"]
        self.norms: list[float] = payload["norms"]
        self.inverted: dict[str, list[list[float]]] = payload["inverted"]
        if len(self.norms) != len(self.chunks):
            raise RagIndexError("metadata and index vector counts do not match")

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
        min_score: float = 0.0,
    ) -> list[RetrievalHit]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        query_vector = _query_vector(query, self.idf)
        if not query_vector:
            return []

        query_norm = _norm(query_vector)
        scores: dict[int, float] = defaultdict(float)
        for term, query_weight in query_vector.items():
            for index, chunk_weight in self.inverted.get(term, []):
                scores[int(index)] += query_weight * float(chunk_weight)

        raw_results: list[tuple[DocumentChunk, float]] = []
        for index, dot_product in scores.items():
            chunk = self.chunks[index]
            if category and chunk.category != category:
                continue
            score = dot_product / (query_norm * self.norms[index])
            if score >= min_score:
                raw_results.append((chunk, score))

        raw_results.sort(key=lambda item: (-item[1], item[0].doc_id, item[0].chunk_id))
        deduped: list[tuple[DocumentChunk, float]] = []
        seen: set[tuple[str, str]] = set()
        for chunk, score in raw_results:
            key = (chunk.doc_id, chunk.text)
            if key in seen:
                continue
            seen.add(key)
            deduped.append((chunk, min(score, 1.0)))
            if len(deduped) == top_k:
                break

        return [
            RetrievalHit(
                content=chunk.text,
                score=round(score, 6),
                rank=rank,
                backend=LEXICAL_BACKEND,
                metadata={
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "source_name": chunk.source_name,
                    "source_url": str(chunk.source_url),
                    "category": chunk.category,
                },
            )
            for rank, (chunk, score) in enumerate(deduped, start=1)
        ]


def _query_vector(query: str, idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(tokenize(query))
    return {term: count * idf[term] for term, count in counts.items() if term in idf}


def _norm(vector: dict[str, float]) -> float:
    return math.sqrt(sum(value * value for value in vector.values())) or 1.0
