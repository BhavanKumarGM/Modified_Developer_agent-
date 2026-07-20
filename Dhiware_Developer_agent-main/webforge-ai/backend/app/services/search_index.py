"""Local semantic search index: chunk + embed project source files into a
per-project SQLite index (using sqlite-vec for the vector similarity
search), incrementally updated so unchanged files are never re-read or
re-embedded.

Embeddings are produced by whatever `embed_fn` the caller passes in —
SearchAgent passes `LLMService.embed`, so this module never talks to Ollama
directly (see the local-first ground rule in LLMService's docstring).
"""
from __future__ import annotations

import hashlib
import sqlite3
import struct
from pathlib import Path
from typing import Awaitable, Callable, Optional

import sqlite_vec

from app.core.config import settings

EmbedFn = Callable[[str], Awaitable[list[float]]]

_SRC_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".py", ".css", ".md"}
_IGNORE_DIRS = {"node_modules", "dist", "build", ".cache", ".git", "__pycache__", ".next"}
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def _index_db_path(project_id: str) -> Path:
    # Kept outside the project root itself so it never ends up in a ZIP
    # download/upload or the file tree — it's a derived cache, not project
    # content.
    index_dir = settings.projects_dir / "_search_index"
    index_dir.mkdir(parents=True, exist_ok=True)
    return index_dir / f"{project_id}.db"


def _connect(project_id: str, embedding_dim: int) -> sqlite3.Connection:
    db = sqlite3.connect(_index_db_path(project_id))
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.execute(
        "CREATE TABLE IF NOT EXISTS files ("
        "  path TEXT PRIMARY KEY,"
        "  mtime REAL NOT NULL,"
        "  content_hash TEXT NOT NULL"
        ")"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS chunks ("
        "  id INTEGER PRIMARY KEY,"
        "  path TEXT NOT NULL,"
        "  chunk_index INTEGER NOT NULL,"
        "  text TEXT NOT NULL"
        ")"
    )
    db.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding FLOAT[{embedding_dim}])"
    )
    db.commit()
    return db


def _chunk_text(text: str, max_chars: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text.strip():
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - overlap
    return chunks


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _serialize(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


class SearchIndex:
    """Owns one project's chunk + embedding index."""

    def __init__(self, project_id: str, embedding_dim: Optional[int] = None) -> None:
        self.project_id = project_id
        self.embedding_dim = embedding_dim or settings.embedding_dim

    async def sync(
        self,
        root: Path,
        embed_fn: EmbedFn,
        _read_files_seen: Optional[list[str]] = None,
    ) -> None:
        """Incrementally (re)index `root`. A file whose mtime hasn't
        changed since the last sync is never read from disk again — this is
        what keeps repeated searches from re-walking + re-reading the whole
        project every call. `_read_files_seen`, if given, gets one entry
        appended per file actually read (for tests to assert on)."""
        db = _connect(self.project_id, self.embedding_dim)
        try:
            existing = {
                row[0]: (row[1], row[2])
                for row in db.execute("SELECT path, mtime, content_hash FROM files")
            }
            seen_paths: set[str] = set()

            for path in root.rglob("*"):
                if any(part in _IGNORE_DIRS for part in path.parts):
                    continue
                if not path.is_file() or path.suffix not in _SRC_EXTENSIONS:
                    continue

                rel = str(path.relative_to(root)).replace("\\", "/")
                seen_paths.add(rel)
                mtime = path.stat().st_mtime

                prior = existing.get(rel)
                if prior is not None and prior[0] == mtime:
                    continue  # unchanged — skip re-reading this file entirely

                if _read_files_seen is not None:
                    _read_files_seen.append(rel)
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                digest = _content_hash(text)
                if prior is not None and prior[1] == digest:
                    # Only the mtime changed (e.g. a touch) — no need to
                    # re-embed, just refresh the watermark.
                    db.execute("UPDATE files SET mtime = ? WHERE path = ?", (mtime, rel))
                    continue

                await self._reindex_file(db, rel, text, digest, mtime, embed_fn)

            # Drop entries for files that were deleted since the last sync.
            for rel in set(existing) - seen_paths:
                self._delete_file_chunks(db, rel)
                db.execute("DELETE FROM files WHERE path = ?", (rel,))

            db.commit()
        finally:
            db.close()

    async def _reindex_file(
        self, db: sqlite3.Connection, rel: str, text: str, digest: str, mtime: float, embed_fn: EmbedFn
    ) -> None:
        self._delete_file_chunks(db, rel)
        for i, chunk in enumerate(_chunk_text(text)):
            try:
                embedding = await embed_fn(chunk)
            except Exception:
                # Embedding model unavailable/unpulled — leave this file
                # un-embedded; SearchAgent still has the keyword heuristic.
                return
            cur = db.execute(
                "INSERT INTO chunks (path, chunk_index, text) VALUES (?, ?, ?)", (rel, i, chunk)
            )
            db.execute(
                "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                (cur.lastrowid, _serialize(embedding)),
            )
        db.execute(
            "INSERT INTO files (path, mtime, content_hash) VALUES (?, ?, ?) "
            "ON CONFLICT(path) DO UPDATE SET mtime = excluded.mtime, content_hash = excluded.content_hash",
            (rel, mtime, digest),
        )

    @staticmethod
    def _delete_file_chunks(db: sqlite3.Connection, rel: str) -> None:
        ids = [row[0] for row in db.execute("SELECT id FROM chunks WHERE path = ?", (rel,))]
        if ids:
            db.executemany("DELETE FROM vec_chunks WHERE rowid = ?", [(i,) for i in ids])
            db.execute("DELETE FROM chunks WHERE path = ?", (rel,))

    async def search(self, query: str, embed_fn: EmbedFn, top_k: int = 8) -> list[str]:
        """Semantic similarity search. Returns relative file paths ranked
        by their best-matching chunk, deduplicated."""
        db = _connect(self.project_id, self.embedding_dim)
        try:
            has_chunks = db.execute("SELECT 1 FROM chunks LIMIT 1").fetchone()
            if not has_chunks:
                return []
            query_embedding = await embed_fn(query)
            rows = db.execute(
                "SELECT chunks.path, vec_chunks.distance "
                "FROM vec_chunks JOIN chunks ON chunks.id = vec_chunks.rowid "
                "WHERE vec_chunks.embedding MATCH ? AND k = ? "
                "ORDER BY vec_chunks.distance",
                (_serialize(query_embedding), max(top_k * 3, top_k)),
            ).fetchall()
        finally:
            db.close()

        ranked: list[str] = []
        for path, _distance in rows:
            if path not in ranked:
                ranked.append(path)
            if len(ranked) >= top_k:
                break
        return ranked
