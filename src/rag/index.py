from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from src.preprocessing import load_corpus
from src.rag.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, split_corpus
from src.rag.models import DocumentChunk

DEFAULT_INDEX_DIR = Path("data/processed/rag")
LEXICAL_BACKEND = "lexical-tfidf-v1"

ASCII_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens = ASCII_WORD_RE.findall(lowered)
    chars = CJK_RE.findall(lowered)
    tokens.extend(chars)
    tokens.extend("".join(chars[index : index + 2]) for index in range(len(chars) - 1))
    return tokens


def build_rag_index(
    *,
    corpus_root: str | Path = "data/raw",
    index_dir: str | Path = DEFAULT_INDEX_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    force: bool = False,
) -> dict[str, object]:
    target = Path(index_dir)
    manifest_path = target / "index_manifest.json"
    if manifest_path.exists() and not force:
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    documents = load_corpus(corpus_root)
    chunks = split_corpus(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        raise ValueError("cannot build RAG index with zero chunks")

    target.mkdir(parents=True, exist_ok=True)
    metadata_path = target / "chunks.json"
    index_path = target / "lexical_index.json"

    chunk_vectors = [_weighted_terms(chunk) for chunk in chunks]
    document_frequency: Counter[str] = Counter()
    for vector in chunk_vectors:
        document_frequency.update(vector.keys())

    chunk_count = len(chunks)
    idf = {
        term: math.log((chunk_count + 1) / (frequency + 1)) + 1
        for term, frequency in document_frequency.items()
    }
    weighted_vectors = [
        {term: value * idf[term] for term, value in vector.items()}
        for vector in chunk_vectors
    ]
    norms = [_norm(vector) for vector in weighted_vectors]
    inverted: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for index, vector in enumerate(weighted_vectors):
        for term, weight in vector.items():
            inverted[term].append((index, weight))

    _write_json_atomic(
        metadata_path,
        [chunk.model_dump(mode="json") for chunk in chunks],
    )
    _write_json_atomic(
        index_path,
        {
            "backend": LEXICAL_BACKEND,
            "idf": idf,
            "norms": norms,
            "inverted": {term: postings for term, postings in sorted(inverted.items())},
        },
    )

    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "embedding_model": LEXICAL_BACKEND,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "document_count": len(documents),
        "chunk_count": chunk_count,
        "index_file": index_path.name,
        "metadata_file": metadata_path.name,
        "source_fingerprint": source_fingerprint(documents),
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def load_chunks(path: str | Path = DEFAULT_INDEX_DIR / "chunks.json") -> list[DocumentChunk]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [DocumentChunk.model_validate(item) for item in payload]


def source_fingerprint(documents: object) -> str:
    payload = [
        {
            "doc_id": document.doc_id,
            "title": document.title,
            "source_url": str(document.source_url),
            "text": document.text,
        }
        for document in sorted(documents, key=lambda item: item.doc_id)
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _weighted_terms(chunk: DocumentChunk) -> Counter[str]:
    terms = tokenize(f"{chunk.title} {chunk.category} {chunk.text}")
    vector = Counter(terms)
    for term in tokenize(chunk.title):
        vector[term] += 2
    return vector


def _norm(vector: dict[str, float]) -> float:
    return math.sqrt(sum(value * value for value in vector.values())) or 1.0


def _write_json_atomic(path: Path, payload: object) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)
