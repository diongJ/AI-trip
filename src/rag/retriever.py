from __future__ import annotations

import json
from json import JSONDecodeError
from collections import defaultdict
from pathlib import Path

from src.rag.index import BM25_BACKEND, DEFAULT_INDEX_DIR, load_chunks, tokenize
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
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except JSONDecodeError as exc:
            raise RagIndexError(
                f"RAG index file is not valid JSON: {index_path}. Rebuild the index."
            ) from exc
        if payload.get("backend") != BM25_BACKEND:
            raise RagIndexError(f"unsupported RAG backend: {payload.get('backend')}")
        self.idf: dict[str, float] = payload["idf"]
        self.lengths: list[float] = payload["lengths"]
        self.average_length: float = payload["average_length"]
        self.k1: float = payload.get("k1", 1.5)
        self.b: float = payload.get("b", 0.75)
        self.inverted: dict[str, list[list[float]]] = payload["inverted"]
        if len(self.lengths) != len(self.chunks):
            raise RagIndexError("metadata and index vector counts do not match")

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
        source_tier: str | None = None,
        min_score: float = 0.0,
    ) -> list[RetrievalHit]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        query_terms = [term for term in dict.fromkeys(tokenize(query)) if term in self.idf]
        if not query_terms:
            return []

        scores: dict[int, float] = defaultdict(float)
        for term in query_terms:
            for index, term_frequency in self.inverted.get(term, []):
                index = int(index)
                frequency = float(term_frequency)
                length_norm = 1 - self.b + self.b * self.lengths[index] / self.average_length
                scores[index] += self.idf[term] * (
                    frequency * (self.k1 + 1) / (frequency + self.k1 * length_norm)
                )

        raw_results: list[tuple[DocumentChunk, float]] = []
        for index, dot_product in scores.items():
            chunk = self.chunks[index]
            if category and chunk.category != category:
                continue
            if source_tier and chunk.source_tier != source_tier:
                continue
            dot_product += _title_overlap_bonus(query_terms, chunk.title)
            score = dot_product / (dot_product + 1.0)
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
                backend=BM25_BACKEND,
                metadata={
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "source_name": chunk.source_name,
                    "source_url": str(chunk.source_url),
                    "category": chunk.category,
                    "source_tier": chunk.source_tier,
                    "topic_tags": chunk.topic_tags,
                    "retrieved_at": chunk.retrieved_at,
                    "published_at": chunk.published_at,
                    "content_hash": chunk.content_hash,
                    "fusion_score": round(score, 6),
                },
            )
            for rank, (chunk, score) in enumerate(deduped, start=1)
        ]

    def search_many(
        self,
        queries: list[str],
        *,
        top_k: int = 8,
        per_query_k: int = 12,
        category: str | None = None,
        source_tier: str | None = None,
    ) -> list[RetrievalHit]:
        """Fuse multiple BM25 result lists with reciprocal-rank fusion."""
        if top_k <= 0 or per_query_k <= 0:
            raise ValueError("top_k and per_query_k must be positive")
        unique_queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))
        fused: dict[str, float] = defaultdict(float)
        hits_by_chunk: dict[str, RetrievalHit] = {}
        for query in unique_queries:
            for hit in self.search(
                query,
                top_k=per_query_k,
                category=category,
                source_tier=source_tier,
            ):
                chunk_id = str(hit.metadata["chunk_id"])
                fused[chunk_id] += 1.0 / (60 + hit.rank)
                current = hits_by_chunk.get(chunk_id)
                if current is None or hit.score > current.score:
                    hits_by_chunk[chunk_id] = hit
        ordered = sorted(fused, key=lambda key: (-fused[key], key))[:top_k]
        max_fusion = max((fused[key] for key in ordered), default=1.0)
        results: list[RetrievalHit] = []
        for rank, chunk_id in enumerate(ordered, start=1):
            hit = hits_by_chunk[chunk_id]
            fusion_score = fused[chunk_id] / max_fusion
            metadata = {**hit.metadata, "fusion_score": round(fusion_score, 6)}
            results.append(
                hit.model_copy(
                    update={
                        "rank": rank,
                        "score": round(min(1.0, fusion_score), 6),
                        "metadata": metadata,
                    }
                )
            )
        return results


def _title_overlap_bonus(query_terms: list[str], title: str) -> float:
    query_bigrams = {term for term in query_terms if len(term) == 2}
    if not query_bigrams:
        return 0.0
    title_terms = set(tokenize(title))
    coverage = len(query_bigrams & title_terms) / len(query_bigrams)
    return 6.0 * coverage
# End of retrieval helpers.
