"""Optional local semantic retrieval layered on top of the stable BM25 index.

The module deliberately imports ML dependencies lazily, so the base offline
demo remains usable without downloading models or installing extra packages.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.rag.models import RetrievalHit
from src.rag.retriever import RagRetriever
from src.rag.retriever import _eligible_for_time

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-base"
SEMANTIC_MANIFEST = "semantic_manifest.json"
SEMANTIC_VECTORS = "semantic_vectors.npy"


class SemanticUnavailable(RuntimeError):
    pass


class SemanticRagRetriever:
    """Fuses lexical and vector recall, then reranks a small candidate set."""

    def __init__(
        self,
        lexical: RagRetriever,
        *,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        reranker_model: str = DEFAULT_RERANKER_MODEL,
    ) -> None:
        self.lexical = lexical
        self.index_dir = lexical.index_dir
        self.idf = lexical.idf  # compatibility with existing focus filters
        self.chunks = lexical.chunks
        self.embedding_model_name = embedding_model
        self.reranker_model_name = reranker_model
        self._encoder: Any | None = None
        self._reranker: Any | None = None
        self._vectors: Any | None = None
        self.reranker_available = False
        self._load_or_build()

    @property
    def available(self) -> bool:
        return self._vectors is not None

    def _load_or_build(self) -> None:
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:
            raise SemanticUnavailable(
                "semantic dependencies are not installed; install .[semantic]"
            ) from exc
        self._encoder = SentenceTransformer(self.embedding_model_name)
        fingerprint = _chunk_fingerprint(self.chunks)
        source_fingerprint = _source_fingerprint(self.index_dir, fingerprint)
        manifest_path = self.index_dir / SEMANTIC_MANIFEST
        vectors_path = self.index_dir / SEMANTIC_VECTORS
        manifest: dict[str, Any] = {}
        if manifest_path.exists() and vectors_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if (
                    manifest.get("embedding_model") == self.embedding_model_name
                    and manifest.get("source_fingerprint") == source_fingerprint
                ):
                    vectors = np.load(vectors_path)
                    if len(vectors) == len(self.chunks):
                        self._vectors = vectors
            except (OSError, ValueError, json.JSONDecodeError):
                self._vectors = None
        if self._vectors is None:
            texts = [f"{chunk.title}\n{chunk.text}" for chunk in self.chunks]
            self._vectors = self._encoder.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            self.index_dir.mkdir(parents=True, exist_ok=True)
            np.save(vectors_path, self._vectors)
            manifest_path.write_text(
                json.dumps(
                    {
                        "embedding_model": self.embedding_model_name,
                        "dimension": int(self._vectors.shape[1]),
                        "chunk_count": len(self.chunks),
                        "chunk_fingerprint": fingerprint,
                        "source_fingerprint": source_fingerprint,
                        "vectors_file": SEMANTIC_VECTORS,
                    },
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
        try:
            from sentence_transformers import CrossEncoder

            self._reranker = CrossEncoder(self.reranker_model_name)
            self.reranker_available = True
        except Exception:
            # Vector recall is still useful if a reranker cannot be loaded.
            self._reranker = None

    def search(self, query: str, **kwargs: Any) -> list[RetrievalHit]:
        kwargs.pop("min_score", None)
        return self.search_many([query], **kwargs)

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
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        lexical_hits = self.lexical.search_many(
            queries,
            top_k=max(per_query_k, top_k),
            per_query_k=per_query_k,
            category=category,
            source_tier=source_tier,
            evidence_role=evidence_role,
            temporal_scope=temporal_scope,
            as_of=as_of,
            zones=zones,
        )
        semantic_hits = self._semantic_hits(
            queries,
            limit=max(per_query_k, top_k),
            category=category,
            source_tier=source_tier,
            evidence_role=evidence_role,
            temporal_scope=temporal_scope,
            as_of=as_of,
            zones=zones,
        )
        candidates = _rrf_merge(lexical_hits, semantic_hits, limit=max(24, top_k * 3))
        candidates = self._rerank(queries[0] if queries else "", candidates)
        return _cap_per_document(candidates, top_k=top_k, per_document=2)

    def _semantic_hits(
        self,
        queries: list[str],
        *,
        limit: int,
        category: str | None,
        source_tier: str | None,
        evidence_role: str | None,
        temporal_scope: str,
        as_of: str | None,
        zones: set[str] | None,
    ) -> list[RetrievalHit]:
        import numpy as np

        if not queries:
            return []
        query_vectors = self._encoder.encode(
            list(dict.fromkeys(query.strip() for query in queries if query.strip())),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        scores = np.max(np.matmul(query_vectors, self._vectors.T), axis=0)
        ordered = sorted(range(len(self.chunks)), key=lambda index: float(scores[index]), reverse=True)
        hits: list[RetrievalHit] = []
        for index in ordered:
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
            score = max(0.0, min(1.0, (float(scores[index]) + 1) / 2))
            metadata = chunk.model_dump(mode="json")
            metadata.update({"fusion_score": score})
            hits.append(
                RetrievalHit(
                    content=chunk.text,
                    score=score,
                    rank=len(hits) + 1,
                    backend="bge-semantic",
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
                        "fusion_score": score,
                    },
                )
            )
            if len(hits) >= limit:
                break
        return hits

    def _rerank(self, query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        if not hits:
            return []
        if self._reranker is None or not query.strip():
            return hits
        try:
            raw_scores = self._reranker.predict([(query, hit.content) for hit in hits])
            pairs = []
            for hit, raw_score in zip(hits, raw_scores, strict=True):
                score = 1 / (1 + math.exp(-float(raw_score)))
                pairs.append((score, hit))
            pairs.sort(key=lambda item: (-item[0], item[1].rank))
            return [
                hit.model_copy(
                    update={
                        "rank": rank,
                        "score": round(score, 6),
                        "backend": "bge-hybrid-reranked",
                        "metadata": {**hit.metadata, "fusion_score": round(score, 6)},
                    }
                )
                for rank, (score, hit) in enumerate(pairs, start=1)
            ]
        except Exception:
            return hits


def _rrf_merge(*ranked_lists: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
    scores: dict[str, float] = defaultdict(float)
    hits: dict[str, RetrievalHit] = {}
    for ranked in ranked_lists:
        for hit in ranked:
            chunk_id = str(hit.metadata["chunk_id"])
            scores[chunk_id] += 1 / (60 + hit.rank)
            if chunk_id not in hits or hit.score > hits[chunk_id].score:
                hits[chunk_id] = hit
    ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))[:limit]
    return [
        hits[chunk_id].model_copy(
            update={
                "rank": rank,
                "score": round(scores[chunk_id] / max(scores.values()), 6),
                "backend": "bm25-bge-hybrid",
            }
        )
        for rank, chunk_id in enumerate(ordered, start=1)
    ]


def _cap_per_document(hits: list[RetrievalHit], *, top_k: int, per_document: int) -> list[RetrievalHit]:
    selected: list[RetrievalHit] = []
    counts: dict[str, int] = defaultdict(int)
    for hit in hits:
        doc_id = str(hit.metadata["doc_id"])
        if counts[doc_id] >= per_document:
            continue
        counts[doc_id] += 1
        selected.append(hit.model_copy(update={"rank": len(selected) + 1}))
        if len(selected) >= top_k:
            break
    return selected


def _chunk_fingerprint(chunks: list[Any]) -> str:
    encoded = "\n".join(
        f"{chunk.chunk_id}:{chunk.title}:{chunk.content_hash}:{chunk.text}" for chunk in chunks
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_fingerprint(index_dir: Path, fallback: str) -> str:
    try:
        manifest = json.loads((index_dir / "index_manifest.json").read_text(encoding="utf-8"))
        return str(manifest.get("source_fingerprint") or fallback)
    except (OSError, ValueError, json.JSONDecodeError):
        return fallback
