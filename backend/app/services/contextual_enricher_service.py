"""
Contextual Enricher — inspired by Anthropic's contextual retrieval paper.

Before embedding, each chunk is prefixed with a structured context block
so the embedding model captures not just what the code does, but where it
lives, what module it belongs to, and what its signature looks like.

This dramatically improves retrieval recall because a query like
"JWT token verification" will now match a function even if the word "JWT"
only appears in the import list or the module path — not in the function body.

Two modes:
  1. Rule-based (default, fast, free): builds context from AST metadata.
  2. LLM-enriched (opt-in via ENABLE_LLM_ENRICHMENT=true): sends chunk to
     Groq to generate a 1-2 sentence plain-English summary appended to the
     rule-based context.
"""
from __future__ import annotations

import os
from typing import Optional

from app.services.ast_chunker_service import CodeChunk
from app.services.observability import log_error


def _infer_module(filename: str) -> str:
    """
    Infer a module/category name from the file path.
    e.g. 'backend/app/auth/jwt_service.py' → 'auth'
         'lib/router/index.js'             → 'router'
    """
    parts = filename.replace("\\", "/").split("/")
    # Walk from the end; take the first non-trivial directory name
    skip = {"app", "src", "lib", "backend", "frontend", ".", ""}
    for part in reversed(parts[:-1]):
        if part.lower() not in skip:
            return part
    return os.path.splitext(parts[-1])[0]


def _build_rule_based_context(chunk: CodeChunk) -> str:
    """
    Build a structured context header from chunk metadata.
    This header is prepended to the raw code before embedding.
    """
    lines = []
    lines.append(f"File: {chunk.filename}")
    lines.append(f"Language: {chunk.language.capitalize()}")

    module = _infer_module(chunk.filename)
    if module:
        lines.append(f"Module: {module}")

    if chunk.chunk_type:
        lines.append(f"Type: {chunk.chunk_type}")

    if chunk.class_name:
        lines.append(f"Class: {chunk.class_name}")

    if chunk.function_name:
        lines.append(f"Function: {chunk.function_name}")

    if chunk.decorators:
        lines.append(f"Decorators: {', '.join(chunk.decorators)}")

    if chunk.imports:
        # Summarize imports to module names only (avoid noise)
        import_names = []
        for imp in chunk.imports[:6]:
            # e.g. "from fastapi import HTTPException" → "fastapi"
            parts = imp.replace("import ", "").replace("from ", "").split()
            if parts:
                import_names.append(parts[0].split(".")[0])
        if import_names:
            lines.append(f"Uses: {', '.join(dict.fromkeys(import_names))}")

    if chunk.docstring:
        lines.append(f"Description: {chunk.docstring[:200]}")

    # Build the final enriched document
    header = "\n".join(lines)
    return f"{header}\n---\n{chunk.raw_content}"


async def _build_llm_context(chunk: CodeChunk, llm_service) -> str:
    """
    Optional: call Groq to generate a one-sentence plain-English summary
    of what this chunk does, then append it to the rule-based header.
    Only invoked when ENABLE_LLM_ENRICHMENT=true.
    """
    try:
        prompt = (
            "In one sentence, describe what this code does. "
            "Be specific about its purpose and any important side effects.\n\n"
            f"```{chunk.language}\n{chunk.raw_content[:800]}\n```\n\nSummary:"
        )
        # Use the existing llm_service general_chat
        summary = llm_service.general_chat(query=prompt, context="")
        if hasattr(summary, "content"):
            summary = summary.content
        summary = str(summary).strip().split("\n")[0]  # first line only
        return summary
    except Exception as e:
        log_error("enricher.llm", error=str(e))
        return ""


class ContextualEnricher:
    """
    Enriches a CodeChunk by prepending structured metadata context
    to its raw content before the embedding is generated.

    The key insight (from Anthropic's paper) is that embedding models
    work much better when the chunk already contains its own context —
    they don't have to infer it from the code alone.
    """

    def __init__(self):
        from app.core.config import settings
        self._enable_llm = settings.ENABLE_LLM_ENRICHMENT
        self._llm_service = None  # lazy import to avoid circular deps

    def _get_llm(self):
        if self._llm_service is None:
            from app.services.llm_service import llm_service
            self._llm_service = llm_service
        return self._llm_service

    def enrich(self, chunk: CodeChunk) -> str:
        """
        Synchronous enrichment (rule-based only).
        Returns the enriched string to use for embedding.
        """
        return _build_rule_based_context(chunk)

    async def enrich_async(self, chunk: CodeChunk) -> str:
        """
        Async enrichment — uses rule-based context plus optional LLM summary.
        Use this in the indexing pipeline for best quality.
        """
        enriched = _build_rule_based_context(chunk)

        if self._enable_llm:
            llm = self._get_llm()
            summary = await _build_llm_context(chunk, llm)
            if summary:
                enriched = enriched + f"\nAI Summary: {summary}"

        return enriched


# Singleton
contextual_enricher = ContextualEnricher()
