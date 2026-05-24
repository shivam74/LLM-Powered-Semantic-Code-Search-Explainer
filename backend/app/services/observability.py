"""
Observability: structured logging and timing utilities for the retrieval pipeline.
All timings are emitted as structured JSON to stdout so Docker can capture them.
"""
import logging
import time
import json
import functools
from typing import Callable, Any

# Configure root logger to emit clean lines
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)

logger = logging.getLogger("semantic_search")


def _emit(event: str, **kwargs):
    """Emit a structured JSON log line."""
    record = {"event": event, **kwargs}
    logger.info(json.dumps(record))


# ── Public helpers ────────────────────────────────────────────────────────────

def log_indexing_start(project_id: str, filename: str):
    _emit("indexing.start", project_id=project_id, filename=filename)


def log_indexing_complete(project_id: str, filename: str, chunk_count: int, elapsed_ms: float):
    _emit(
        "indexing.complete",
        project_id=project_id,
        filename=filename,
        chunk_count=chunk_count,
        elapsed_ms=round(elapsed_ms, 2),
    )


def log_retrieval(
    query: str,
    project_id: str,
    vector_ms: float,
    bm25_ms: float,
    rerank_ms: float,
    total_ms: float,
    result_count: int,
):
    _emit(
        "retrieval.complete",
        project_id=project_id,
        query=query[:80],  # truncate for log brevity
        vector_ms=round(vector_ms, 2),
        bm25_ms=round(bm25_ms, 2),
        rerank_ms=round(rerank_ms, 2),
        total_ms=round(total_ms, 2),
        result_count=result_count,
    )


def log_chunking(filename: str, strategy: str, chunk_count: int, elapsed_ms: float):
    _emit(
        "chunking.complete",
        filename=filename,
        strategy=strategy,  # "ast" or "fallback"
        chunk_count=chunk_count,
        elapsed_ms=round(elapsed_ms, 2),
    )


def log_error(event: str, error: str, **kwargs):
    _emit(f"{event}.error", error=error, **kwargs)


class Timer:
    """Context manager that measures elapsed time in milliseconds."""
    def __init__(self):
        self.elapsed_ms: float = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
