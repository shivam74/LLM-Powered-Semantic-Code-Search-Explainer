"""
Cross-encoder reranker using HuggingFace Inference API.

Disabled by default (ENABLE_RERANKER=false in config) to keep latency low.
When enabled, calls BAAI/bge-reranker-base via the HF Inference REST API
— no local model download required.

The reranker receives (query, passage) pairs and scores their relevance
on a 0-1 scale.  We use it to re-order the top-20 fusion candidates
and return the top-5 most relevant.

If the API call fails (rate-limit, network error, etc.) the service
silently falls back to the pre-reranked ordering so retrieval never fails.
"""
from __future__ import annotations

from typing import List, Tuple

import httpx

from app.services.observability import log_error, Timer


class RerankerService:

    def __init__(self):
        from app.core.config import settings
        self._enabled = settings.ENABLE_RERANKER
        self._model = settings.RERANKER_MODEL
        self._hf_token = settings.HUGGINGFACE_API_KEY
        self._api_url = (
            f"https://api-inference.huggingface.co/models/{self._model}"
        )

    async def rerank(
        self,
        query: str,
        candidates: List[Tuple[str, float, str]],  # (chunk_id, score, raw_content)
        top_k: int = 5,
    ) -> List[Tuple[str, float, str]]:
        """
        Rerank `candidates` by relevance to `query`.

        Returns the top_k most relevant candidates sorted by reranker score.
        On any failure, returns the original list truncated to top_k.
        """
        if not self._enabled or not candidates:
            return candidates[:top_k]

        with Timer() as t:
            try:
                scores = await self._call_api(query, candidates)
            except Exception as e:
                log_error("reranker.api", error=str(e))
                return candidates[:top_k]

        # Pair candidates with reranker scores, sort descending
        paired = sorted(
            zip(candidates, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        result = [cand for cand, _ in paired[:top_k]]
        return result

    async def _call_api(
        self,
        query: str,
        candidates: List[Tuple[str, float, str]],
    ) -> List[float]:
        """
        Call the HuggingFace Inference API for text-classification reranking.
        BAAI/bge-reranker-base accepts {text, text_pair} inputs and returns
        a relevance score.
        """
        headers = {"Authorization": f"Bearer {self._hf_token}"}

        # Build input pairs — (query, passage) per candidate
        inputs = [
            {"text": query[:512], "text_pair": cand[2][:512]}
            for cand in candidates
        ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._api_url,
                headers=headers,
                json={"inputs": inputs},
            )
            response.raise_for_status()
            data = response.json()

        # Parse response: list of [{label, score}] per input
        scores = []
        for item in data:
            if isinstance(item, list):
                # Take the score of the positive label
                pos = next(
                    (x["score"] for x in item if x["label"] in ("LABEL_1", "entailment")),
                    0.0,
                )
                scores.append(pos)
            elif isinstance(item, dict):
                scores.append(item.get("score", 0.0))
            else:
                scores.append(0.0)

        # Pad if API returned fewer scores than inputs
        while len(scores) < len(candidates):
            scores.append(0.0)

        return scores


# Singleton
reranker_service = RerankerService()
