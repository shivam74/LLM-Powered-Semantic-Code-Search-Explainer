"""
Hybrid Retrieval Service — the main orchestrator.

Pipeline:
  query
    → vector search (ChromaDB)    top-K dense hits
    → BM25 search                 top-K sparse hits
    → RRF fusion                  merge + deduplicate
    → reranker (optional)         cross-encoder re-order
    → return top-N results

Reciprocal Rank Fusion (RRF):
  score(d) = Σ  1 / (k + rank(d))
  k = 60 is standard; chosen to balance early-rank emphasis.

Why RRF over weighted score addition?
  - Vector scores and BM25 scores have incompatible scales.
  - RRF is score-free — it only uses ranks, making it robust and
    requiring no normalisation.  Weighted score addition is offered
    as an alternative via use_score_fusion=True.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.services.bm25_service import bm25_service
from app.services.reranker_service import reranker_service
from app.services.vector_db_service import vector_db
from app.services.observability import Timer, log_retrieval


@dataclass
class RetrievalResult:
    """Unified result object returned to API routes."""
    chunk_id: str
    raw_content: str
    metadata: dict
    vector_score: float = 0.0
    bm25_score: float = 0.0
    fusion_score: float = 0.0
    rerank_score: Optional[float] = None


# ── RRF implementation ────────────────────────────────────────────────────────

_RRF_K = 60  # standard constant


def _rrf_merge(
    vector_results: list,   # [(chunk_id, norm_score, raw_content, metadata), ...]
    bm25_results: list,     # [(chunk_id, norm_score, raw_content), ...]
    vector_weight: float,
    bm25_weight: float,
) -> List[RetrievalResult]:
    """
    Merge vector and BM25 results using Reciprocal Rank Fusion.
    Returns a deduplicated list sorted by fusion score descending.
    """
    # Track individual scores for debugging
    chunk_data: dict[str, dict] = {}          # chunk_id → {raw_content, metadata}
    vector_scores: dict[str, float] = {}
    bm25_scores: dict[str, float] = {}
    rrf_scores: dict[str, float] = defaultdict(float)

    # Process vector results (ranked list)
    for rank, (cid, vscore, raw, meta) in enumerate(vector_results):
        rrf_scores[cid] += vector_weight / (_RRF_K + rank + 1)
        vector_scores[cid] = vscore
        chunk_data[cid] = {"raw_content": raw, "metadata": meta}

    # Process BM25 results
    for rank, (cid, bscore, raw) in enumerate(bm25_results):
        rrf_scores[cid] += bm25_weight / (_RRF_K + rank + 1)
        bm25_scores[cid] = bscore
        if cid not in chunk_data:
            chunk_data[cid] = {"raw_content": raw, "metadata": {}}

    # Build sorted result list
    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

    results = []
    for cid in sorted_ids:
        data = chunk_data[cid]
        results.append(RetrievalResult(
            chunk_id=cid,
            raw_content=data["raw_content"],
            metadata=data["metadata"],
            vector_score=vector_scores.get(cid, 0.0),
            bm25_score=bm25_scores.get(cid, 0.0),
            fusion_score=rrf_scores[cid],
        ))

    return results


# ── Service ───────────────────────────────────────────────────────────────────

class HybridRetrievalService:
    """
    The single entry-point for all retrieval operations.

    Usage:
        results = await hybrid_retrieval.search(query, project_id)
    """

    def __init__(self):
        from app.core.config import settings
        self._vector_weight = settings.VECTOR_WEIGHT
        self._bm25_weight = settings.BM25_WEIGHT
        self._candidate_k = settings.RETRIEVAL_CANDIDATE_K
        self._top_k = settings.RETRIEVAL_TOP_K

    async def search(
        self,
        query: str,
        project_id: Optional[str],
        top_k: Optional[int] = None,
        debug: bool = False,
    ) -> List[RetrievalResult]:
        """
        Run the full hybrid retrieval pipeline.

        Args:
            query:      Natural language or code query.
            project_id: Scope results to this project.
            top_k:      Override default RETRIEVAL_TOP_K.
            debug:      If True, return all candidates (skips reranking truncation).

        Returns:
            Sorted list of RetrievalResult, best match first.
        """
        final_k = top_k or self._top_k
        candidate_k = self._candidate_k

        t_total = Timer()
        t_vector = Timer()
        t_bm25 = Timer()
        t_rerank = Timer()

        t_total.__enter__()

        # ── 1. Dense vector retrieval ─────────────────────────────────────
        with t_vector:
            raw_vector = vector_db.search(
                query=query,
                project_id=project_id,
                top_k=candidate_k,
            )
            # raw_vector: List[Tuple[Document, distance_score]]
            # ChromaDB returns L2 distance. Convert to a similarity in (0,1].
            # Use 1/(1+dist) instead of 1-(dist/max) so a single result doesn't
            # normalise to 0.0 and multiple results stay meaningfully ordered.
            vector_list = []
            for doc, dist in raw_vector:
                # Prefer the stored chunk_id in metadata (written by file_parser_service)
                cid = doc.metadata.get(
                    "chunk_id",
                    f"{doc.metadata.get('filename','f')}_{doc.metadata.get('chunk_index', 0)}"
                )
                norm_score = 1.0 / (1.0 + dist)   # always in (0,1], monotone w.r.t. similarity
                vector_list.append((cid, norm_score, doc.page_content, doc.metadata))

        # ── 2. Sparse BM25 retrieval ──────────────────────────────────────
        with t_bm25:
            bm25_raw = []
            if project_id:
                bm25_raw = await bm25_service.search(
                    query=query,
                    project_id=project_id,
                    top_k=candidate_k,
                )
            # bm25_raw: List[Tuple[chunk_id, norm_score, raw_content]]

        # ── 3. RRF fusion ─────────────────────────────────────────────────
        merged = _rrf_merge(
            vector_list,
            bm25_raw,
            self._vector_weight,
            self._bm25_weight,
        )

        if debug:
            t_total.__exit__(None, None, None)
            return merged  # return all candidates for debug endpoint

        # ── 4. Reranking (optional) ───────────────────────────────────────
        with t_rerank:
            # Convert to reranker's input format: (chunk_id, score, raw_content)
            rerank_input = [
                (r.chunk_id, r.fusion_score, r.raw_content)
                for r in merged[:candidate_k]
            ]
            reranked = await reranker_service.rerank(
                query=query,
                candidates=rerank_input,
                top_k=final_k,
            )
            # Map back to RetrievalResult by chunk_id
            reranked_ids = {cid: i for i, (cid, _, _) in enumerate(reranked)}
            final_results = []
            for r in merged:
                if r.chunk_id in reranked_ids:
                    final_results.append(r)
            # Sort by reranker's order
            final_results.sort(key=lambda r: reranked_ids.get(r.chunk_id, 999))

        t_total.__exit__(None, None, None)

        log_retrieval(
            query=query,
            project_id=project_id or "global",
            vector_ms=t_vector.elapsed_ms,
            bm25_ms=t_bm25.elapsed_ms,
            rerank_ms=t_rerank.elapsed_ms,
            total_ms=t_total.elapsed_ms,
            result_count=len(final_results),
        )

        return final_results[:final_k]


# Singleton
hybrid_retrieval = HybridRetrievalService()
