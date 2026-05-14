"""Optional semantic search subsystem.

Lazy-loaded; importing this module does NOT pull sentence-transformers
unless :func:`SemanticIndex.ensure_model` is invoked.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..config import SemanticSearchConfig
from ..errors import DokumenPintarError


@dataclass(frozen=True)
class SemanticHit:
    rank: int
    score: float
    doc_path: str
    chunk_index: int
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "score": self.score,
            "doc_path": self.doc_path,
            "chunk_index": self.chunk_index,
            "snippet": self.snippet,
        }


_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL,
    indexed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks (doc_path);
"""


def _chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(text), step):
        piece = text[i : i + chunk_size]
        if piece.strip():
            chunks.append(piece)
        if i + chunk_size >= len(text):
            break
    return chunks


class SemanticIndex:
    """SQLite-backed nearest-neighbour search over text chunks."""

    def __init__(self, config: SemanticSearchConfig, *, default_path: Path):
        self._config = config
        self._db_path = (
            Path(config.index_path).expanduser().resolve() if config.index_path else default_path
        )
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._model = None  # lazy
        self._np = None  # lazy numpy
        self._init_db()

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def db_path(self) -> Path:
        return self._db_path

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            import numpy as np  # noqa: WPS433
            from sentence_transformers import SentenceTransformer  # noqa: WPS433
        except ImportError as exc:  # pragma: no cover
            raise DokumenPintarError(
                "Semantic search requires the 'semantic' extra. "
                "Install with: pip install dokumen-pintar[semantic]"
            ) from exc
        self._np = np
        self._model = SentenceTransformer(self._config.model)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    def index_document(self, doc_path: str, text: str) -> int:
        if not self.enabled:
            return 0
        self.ensure_model()
        assert self._model is not None and self._np is not None
        chunks = _chunk_text(
            text,
            chunk_size=self._config.chunk_size,
            overlap=self._config.chunk_overlap,
        )
        if not chunks:
            return 0
        embeddings = self._model.encode(chunks, normalize_embeddings=True)
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM chunks WHERE doc_path = ?", (doc_path,))
            for idx, (chunk, vec) in enumerate(zip(chunks, embeddings)):
                conn.execute(
                    "INSERT INTO chunks(doc_path, chunk_index, text, embedding, indexed_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (doc_path, idx, chunk, self._np.asarray(vec, dtype="float32").tobytes(), ts),
                )
        return len(chunks)

    def remove_document(self, doc_path: str) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM chunks WHERE doc_path = ?", (doc_path,))
            return cur.rowcount

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def search(self, query: str, *, top_k: int = 10) -> list[SemanticHit]:
        if not self.enabled:
            return []
        self.ensure_model()
        assert self._model is not None and self._np is not None
        q_vec = self._np.asarray(
            self._model.encode([query], normalize_embeddings=True)[0], dtype="float32"
        )
        rows = self._all_rows()
        if not rows:
            return []
        # Compute cosine similarity (vectors are already L2-normalised).
        embs = self._np.stack([self._np.frombuffer(r["embedding"], dtype="float32") for r in rows])
        scores = embs @ q_vec
        order = self._np.argsort(-scores)[: max(0, top_k)]
        hits: list[SemanticHit] = []
        for rank, idx in enumerate(order, start=1):
            r = rows[int(idx)]
            text = r["text"]
            snippet = text if len(text) <= 240 else text[:237] + "..."
            hits.append(
                SemanticHit(
                    rank=rank,
                    score=float(scores[int(idx)]),
                    doc_path=r["doc_path"],
                    chunk_index=int(r["chunk_index"]),
                    snippet=snippet,
                )
            )
        return hits

    def stats(self) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            docs = conn.execute("SELECT COUNT(DISTINCT doc_path) FROM chunks").fetchone()[0]
        return {
            "enabled": self.enabled,
            "model": self._config.model,
            "chunks": total,
            "documents": docs,
            "db_path": str(self._db_path),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _all_rows(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            cur = conn.execute("SELECT doc_path, chunk_index, text, embedding FROM chunks")
            return [
                {
                    "doc_path": p,
                    "chunk_index": ci,
                    "text": t,
                    "embedding": e,
                }
                for (p, ci, t, e) in cur.fetchall()
            ]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(_SCHEMA)


def serialize_hits(hits: Iterable[SemanticHit]) -> str:
    return json.dumps([h.to_dict() for h in hits], indent=2)
