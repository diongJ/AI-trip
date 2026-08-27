from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo
from json import JSONDecodeError
from collections import defaultdict
from pathlib import Path

from src.rag.index import BM25_BACKEND, DEFAULT_INDEX_DIR, load_chunks, tokenize
from src.rag.models import DocumentChunk, RetrievalHit


class RagIndexError(RuntimeError):
    pass


# Normalized-score floor for a hit to count as relevant evidence.
MIN_RELEVANT_SCORE = 0.12
# Stricter floor when the query has no multi-character terms (single-character query).
SINGLE_TERM_SCORE_FLOOR = 0.30


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
        evidence_role: str | None = None,
        min_score: float = 0.0,
        temporal_scope: str = "all",
        as_of: str | None = None,
        zones: set[str] | None = None,
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

        # Relevance gate: a chunk must contain enough distinct multi-character
        # query terms (CJK bigrams or ASCII words). Single-character matches,
        # or one incidental bigram inside a long query, are too noisy to serve
        # as grounded evidence.
        gate_terms = [term for term in query_terms if len(term) >= 2]
        min_gate_hits = 1 if len(gate_terms) <= 2 else 2
        gate_hit_count: dict[int, int] = defaultdict(int)
        for term in gate_terms:
            for index, _term_frequency in self.inverted.get(term, []):
                gate_hit_count[int(index)] += 1
        gated_indices: set[int] | None = None
        if gate_terms:
            gated_indices = {
                index for index, count in gate_hit_count.items() if count >= min_gate_hits
            }
        score_floor = max(
            min_score,
            MIN_RELEVANT_SCORE if gate_terms else SINGLE_TERM_SCORE_FLOOR,
        )

        raw_results: list[tuple[DocumentChunk, float]] = []
        for index, dot_product in scores.items():
            if gated_indices is not None and index not in gated_indices:
                continue
            chunk = self.chunks[index]
            if category and chunk.category != category:
                continue
            if source_tier and chunk.source_tier != source_tier:
                continue
            if evidence_role and chunk.evidence_role != evidence_role:
                continue
            if not _eligible_for_time(chunk, temporal_scope=temporal_scope, as_of=as_of):
                continue
            if zones and chunk.zone and chunk.zone not in zones:
                continue
            dot_product += _title_overlap_bonus(query_terms, chunk.title)
            score = dot_product / (dot_product + 1.0)
            if score >= score_floor:
                raw_results.append((chunk, score))

        raw_results.sort(key=lambda item: (-item[1], item[0].doc_id, item[0].chunk_id))
        if not raw_results:
            return []
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

        return [_hit_from_chunk(chunk, score, rank) for rank, (chunk, score) in enumerate(deduped, start=1)]

    def search_many(
        self,
        queries: list[str],
        *,
        top_k: int = 8,
        per_query_k: int = 12,
        category: str | None = None,
        source_tier: str | None = None,
        evidence_role: str | None = None,
        temporal_scope: str = "all",
        as_of: str | None = None,
        zones: set[str] | None = None,
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
                evidence_role=evidence_role,
                temporal_scope=temporal_scope,
                as_of=as_of,
                zones=zones,
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


def _hit_from_chunk(chunk: DocumentChunk, score: float, rank: int) -> RetrievalHit:
    rounded_score = round(min(score, 1.0), 6)
    return RetrievalHit(
        content=chunk.text,
        score=rounded_score,
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
            "source_type": chunk.source_type,
            "evidence_role": chunk.evidence_role,
            "review_status": chunk.review_status,
            "topic_tags": chunk.topic_tags,
            "retrieved_at": chunk.retrieved_at,
            "published_at": chunk.published_at,
            "content_hash": chunk.content_hash,
            "effective_from": chunk.effective_from,
            "effective_until": chunk.effective_until,
            "last_checked_at": chunk.last_checked_at,
            "volatility": chunk.volatility,
            "zone": chunk.zone,
            "floor": chunk.floor,
            "visitor_types": chunk.visitor_types,
            "recommended_duration": chunk.recommended_duration,
            "fusion_score": rounded_score,
        },
    )


def _eligible_for_time(chunk: DocumentChunk, *, temporal_scope: str, as_of: str | None) -> bool:
    if temporal_scope == "all":
        return True
    try:
        target = datetime.fromisoformat(as_of).date() if as_of else datetime.now(ZoneInfo("Asia/Shanghai")).date()
        start = datetime.fromisoformat(chunk.effective_from).date() if chunk.effective_from else None
        end = datetime.fromisoformat(chunk.effective_until).date() if chunk.effective_until else None
    except ValueError:
        return False
    if temporal_scope == "historical":
        return (start is None or start <= target) and (end is None or target <= end)
    if temporal_scope == "future":
        # “未来/即将” without an explicit date is a request for upcoming
        # notices. With a date, retrieve rules that will actually be valid on
        # that day (including stable visitor facts), not only those starting
        # after it.
        if as_of is None:
            return start is not None and start >= target and chunk.volatility != "expired"
        return (
            chunk.volatility != "expired"
            and (start is None or start <= target)
            and (end is None or target <= end)
        )
    # Current is deliberately conservative: expired notices and rules not yet in
    # force never compete with stable visitor guidance.
    return (
        chunk.volatility != "expired"
        and (start is None or start <= target)
        and (end is None or target <= end)
    )
