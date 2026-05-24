"""
File Parser Service — thin orchestration wrapper.

Replaces the old RecursiveCharacterTextSplitter-based parser.
Now delegates to ASTChunkerService + ContextualEnricher and returns
everything the indexing pipeline needs in one call.
"""
from __future__ import annotations

from typing import List, Tuple

from app.services.ast_chunker_service import CodeChunk, ast_chunker
from app.services.contextual_enricher_service import contextual_enricher


class FileParserService:

    async def parse_and_enrich(
        self,
        file_content: str,
        filename: str,
        project_id: str,
    ) -> List[Tuple[str, str, dict, str]]:
        """
        Parse a file and enrich every chunk for indexing.

        Returns a list of tuples:
            (enriched_text, raw_content, metadata_dict, chunk_id)

        - enriched_text → stored in ChromaDB as the embedding source
        - raw_content   → stored in metadata["raw_content"] for display
        - metadata_dict → all chunk metadata (filename, language, etc.)
        - chunk_id      → stable ID used for dedup and deletion
        """
        chunks: List[CodeChunk] = ast_chunker.chunk(file_content, filename, project_id)

        results = []
        for chunk in chunks:
            enriched = await contextual_enricher.enrich_async(chunk)
            meta = chunk.to_metadata()
            meta["raw_content"] = chunk.raw_content

            # Stable chunk ID: filename + index ensures safe deletion by file
            chunk_id = f"{filename}_{chunk.chunk_index}"
            meta["chunk_id"] = chunk_id  # store so retrieval service can read it back directly

            results.append((enriched, chunk.raw_content, meta, chunk_id))

        return results


# Singleton (kept for backward compatibility — old name still importable)
file_parser = FileParserService()
