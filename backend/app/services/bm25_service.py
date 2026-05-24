"""
BM25 sparse retrieval service.

Maintains a per-project BM25 index built from raw chunk text.
The corpus is persisted in MongoDB so it survives container restarts.
In-memory BM25Okapi instances are cached in a dict keyed by project_id.

Design:
  - "bm25_indices" MongoDB collection stores one document per project
    containing a list of {chunk_id, tokens, raw_content} records.
  - On first search for a project, the corpus is loaded from Mongo and
    a BM25Okapi instance is built and cached.
  - When files are added/deleted the in-memory cache is invalidated and
    the Mongo document is updated atomically.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from app.services.observability import log_error

# ── Tokeniser ─────────────────────────────────────────────────────────────────

def _tokenise(text: str) -> List[str]:
    """
    Simple whitespace + punctuation tokeniser.
    Lowercases and splits on non-alphanumeric chars.
    camelCase / snake_case are split into sub-tokens for better recall.
    """
    # Split camelCase: HTTPRequest → HTTP Request
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    # Split on non-alphanumeric
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    # Remove very short tokens
    return [t for t in tokens if len(t) > 1]


# ── BM25 index entry ──────────────────────────────────────────────────────────

class _ChunkRecord:
    __slots__ = ("chunk_id", "tokens", "raw_content")

    def __init__(self, chunk_id: str, tokens: List[str], raw_content: str):
        self.chunk_id = chunk_id
        self.tokens = tokens
        self.raw_content = raw_content


# ── Service ───────────────────────────────────────────────────────────────────

class BM25Service:
    """
    Manages BM25 indexes for all projects.
    Thread-safe for reads; writes should be serialised at the caller level
    (FastAPI's async event loop ensures single-threaded coroutine execution).
    """

    def __init__(self):
        # {project_id: BM25Okapi}
        self._index_cache: dict = {}
        # {project_id: List[_ChunkRecord]}  – mirrors the Mongo corpus
        self._corpus_cache: dict = {}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_db(self):
        from app.db.database import get_database
        return get_database()

    def _build_bm25(self, records: List[_ChunkRecord]):
        try:
            from rank_bm25 import BM25Okapi
            corpus = [r.tokens for r in records]
            return BM25Okapi(corpus) if corpus else None
        except ImportError:
            log_error("bm25.import", error="rank-bm25 not installed")
            return None

    async def _load_corpus(self, project_id: str) -> List[_ChunkRecord]:
        """Load corpus from MongoDB and rebuild the in-memory BM25 index."""
        db = self._get_db()
        doc = await db.bm25_indices.find_one({"project_id": project_id})
        if not doc:
            return []
        records = [
            _ChunkRecord(
                chunk_id=c["chunk_id"],
                tokens=c["tokens"],
                raw_content=c.get("raw_content", ""),
            )
            for c in doc.get("chunks", [])
        ]
        return records

    async def _ensure_loaded(self, project_id: str):
        """Ensure the in-memory index for project_id exists."""
        if project_id not in self._corpus_cache:
            records = await self._load_corpus(project_id)
            self._corpus_cache[project_id] = records
            self._index_cache[project_id] = self._build_bm25(records)

    # ── Public API ────────────────────────────────────────────────────────────

    async def add_chunks(
        self,
        project_id: str,
        chunk_ids: List[str],
        raw_contents: List[str],
    ):
        """
        Add new chunks to the BM25 index for a project.
        chunk_ids must correspond 1-to-1 with raw_contents.
        """
        db = self._get_db()

        new_records = []
        for cid, content in zip(chunk_ids, raw_contents):
            tokens = _tokenise(content)
            new_records.append({
                "chunk_id": cid,
                "tokens": tokens,
                "raw_content": content[:2000],  # cap stored content
            })

        # Upsert into MongoDB
        await db.bm25_indices.update_one(
            {"project_id": project_id},
            {"$push": {"chunks": {"$each": new_records}}},
            upsert=True,
        )

        # Invalidate in-memory cache so it's rebuilt on next search
        self._corpus_cache.pop(project_id, None)
        self._index_cache.pop(project_id, None)

    async def remove_by_filename(self, project_id: str, filename: str):
        """Remove all chunks belonging to a file from the BM25 index."""
        db = self._get_db()
        # chunk_ids are prefixed with filename
        await db.bm25_indices.update_one(
            {"project_id": project_id},
            {"$pull": {"chunks": {"chunk_id": {"$regex": f"^{re.escape(filename)}_"}}}},
        )
        self._corpus_cache.pop(project_id, None)
        self._index_cache.pop(project_id, None)

    async def remove_project(self, project_id: str):
        """Delete the entire BM25 index for a project."""
        db = self._get_db()
        await db.bm25_indices.delete_one({"project_id": project_id})
        self._corpus_cache.pop(project_id, None)
        self._index_cache.pop(project_id, None)

    async def search(
        self,
        query: str,
        project_id: str,
        top_k: int = 20,
    ) -> List[Tuple[str, float, str]]:
        """
        BM25 search over all indexed chunks for a project.
        Returns list of (chunk_id, normalised_score, raw_content).
        """
        await self._ensure_loaded(project_id)
        bm25 = self._index_cache.get(project_id)
        records = self._corpus_cache.get(project_id, [])

        if bm25 is None or not records:
            return []

        query_tokens = _tokenise(query)
        if not query_tokens:
            return []

        scores = bm25.get_scores(query_tokens)
        max_score = max(scores) if scores.any() else 1.0

        # Pair (record, score) and sort descending
        paired = sorted(zip(records, scores), key=lambda x: x[1], reverse=True)

        results = []
        for record, score in paired[:top_k]:
            norm_score = float(score) / max_score if max_score > 0 else 0.0
            results.append((record.chunk_id, norm_score, record.raw_content))

        return results

    async def rebuild_index(self, project_id: str):
        """Force a full reload from MongoDB (used after re-indexing)."""
        self._corpus_cache.pop(project_id, None)
        self._index_cache.pop(project_id, None)
        await self._ensure_loaded(project_id)


# Singleton
bm25_service = BM25Service()
