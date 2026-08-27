from __future__ import annotations

import re
from collections.abc import Iterable

from src.preprocessing import CorpusDocument
from src.rag.models import DocumentChunk

DEFAULT_CHUNK_SIZE = 420
DEFAULT_CHUNK_OVERLAP = 60
MIN_CHUNK_LENGTH = 12

PARAGRAPH_RE = re.compile(r"\n+")
SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    lines = [WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def split_document(
    document: CorpusDocument,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size")

    paragraphs = [
        paragraph.strip()
        for paragraph in PARAGRAPH_RE.split(normalize_text(document.text))
        if paragraph.strip()
    ]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        pieces = _split_long_text(paragraph, chunk_size)
        for piece in pieces:
            if not current:
                current = piece
            elif len(current) + len(piece) + 1 <= chunk_size:
                current = f"{current}\n{piece}"
            else:
                chunks.append(current)
                current = _with_overlap(current, chunk_overlap, piece)

    if current:
        chunks.append(current)

    unique_chunks: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        cleaned = normalize_text(chunk).strip()
        if len(cleaned) < MIN_CHUNK_LENGTH or cleaned in seen:
            continue
        seen.add(cleaned)
        unique_chunks.append(cleaned)

    return [
        DocumentChunk(
            chunk_id=f"{document.doc_id}_CHUNK_{index:03d}",
            text=chunk,
            doc_id=document.doc_id,
            title=document.title,
            source_name=document.source_name,
            source_url=str(document.source_url),
            category=document.category,
            source_tier=document.source_tier,
            source_type=document.source_type,
            evidence_role=document.evidence_role,
            review_status=document.review_status,
            topic_tags=document.topic_tags,
            retrieved_at=document.retrieved_at,
            published_at=document.published_at,
            content_hash=document.content_hash,
            effective_from=document.effective_from,
            effective_until=document.effective_until,
            last_checked_at=document.last_checked_at,
            volatility=document.volatility,
            zone=document.zone,
            floor=document.floor,
            visitor_types=document.visitor_types,
            recommended_duration=document.recommended_duration,
        )
        for index, chunk in enumerate(unique_chunks, start=1)
    ]


def split_corpus(
    documents: Iterable[CorpusDocument],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    seen_ids: set[str] = set()
    for document in sorted(documents, key=lambda item: item.doc_id):
        for chunk in split_document(
            document, chunk_size=chunk_size, chunk_overlap=chunk_overlap
        ):
            if chunk.chunk_id in seen_ids:
                raise ValueError(f"duplicate chunk_id: {chunk.chunk_id}")
            seen_ids.add(chunk.chunk_id)
            chunks.append(chunk)
    return chunks


def _split_long_text(text: str, chunk_size: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    sentences = [sentence.strip() for sentence in SENTENCE_RE.split(text) if sentence.strip()]
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > chunk_size:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_hard_split(sentence, chunk_size))
        elif not current:
            current = sentence
        elif len(current) + len(sentence) <= chunk_size:
            current += sentence
        else:
            pieces.append(current)
            current = sentence
    if current:
        pieces.append(current)
    return pieces


def _hard_split(text: str, chunk_size: int) -> list[str]:
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


def _with_overlap(previous: str, overlap: int, next_piece: str) -> str:
    if overlap == 0:
        return next_piece
    prefix = previous[-overlap:].strip()
    return f"{prefix}\n{next_piece}" if prefix else next_piece
