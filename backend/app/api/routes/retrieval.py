"""
Retrieval debug endpoints — inspect chunk metadata, scores, and index stats.
These endpoints are for development/debugging and do not affect the frontend.
"""
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from typing import List

from app.api.dependencies import get_current_user
from app.schemas.user import UserResponse
from app.schemas.retrieval import (
    DebugSearchQuery, DebugSearchResponse, DebugSearchResult, ProjectStats
)
from app.db.database import get_database
from app.services.hybrid_retrieval_service import hybrid_retrieval
from app.services.vector_db_service import vector_db
from app.services.bm25_service import bm25_service
from app.services.file_parser_service import file_parser
from app.services.observability import log_error

router = APIRouter()


@router.post("/debug", response_model=DebugSearchResponse)
async def debug_search(
    query: DebugSearchQuery,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Returns ALL retrieval candidates with individual vector, BM25, and fusion
    scores — useful for tuning weights and understanding ranking decisions.
    """
    db = get_database()
    project = await db.projects.find_one({
        "_id": ObjectId(query.project_id), "owner_id": current_user.id
    })
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # debug=True returns all candidates without reranking truncation
    candidates = await hybrid_retrieval.search(
        query=query.query,
        project_id=query.project_id,
        top_k=query.top_k,
        debug=True,
    )

    results = [
        DebugSearchResult(
            chunk_id=r.chunk_id,
            raw_content=r.raw_content[:500],  # truncate for readability
            metadata=r.metadata,
            vector_score=round(r.vector_score, 6),
            bm25_score=round(r.bm25_score, 6),
            fusion_score=round(r.fusion_score, 6),
        )
        for r in candidates[:query.top_k]
    ]

    return DebugSearchResponse(
        query=query.query,
        results=results,
        total_candidates=len(candidates),
    )


@router.get("/chunks/{project_id}")
async def list_chunks(
    project_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """List all indexed chunk metadata for a project (no raw content)."""
    db = get_database()
    project = await db.projects.find_one({
        "_id": ObjectId(project_id), "owner_id": current_user.id
    })
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chunks = vector_db.list_chunks(project_id)
    # Strip raw_content from metadata to keep response lean
    for c in chunks:
        c["metadata"].pop("raw_content", None)

    return {"project_id": project_id, "total": len(chunks), "chunks": chunks}


@router.get("/stats/{project_id}", response_model=ProjectStats)
async def project_stats(
    project_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Return indexing statistics for a project."""
    db = get_database()
    project = await db.projects.find_one({
        "_id": ObjectId(project_id), "owner_id": current_user.id
    })
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chunks = vector_db.list_chunks(project_id)
    languages = list({c["metadata"].get("language", "unknown") for c in chunks})
    files = list({c["metadata"].get("filename", "") for c in chunks})

    # BM25 count from Mongo
    bm25_doc = await db.bm25_indices.find_one({"project_id": project_id})
    bm25_count = len(bm25_doc.get("chunks", [])) if bm25_doc else 0

    return ProjectStats(
        project_id=project_id,
        total_chunks=len(chunks),
        bm25_indexed=bm25_count,
        languages=sorted(languages),
        files=sorted(files),
    )


@router.post("/reindex/{project_id}")
async def reindex_project(
    project_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Re-index all files in a project using the current pipeline.
    Useful after upgrading the chunking/enrichment logic.
    Deletes existing vectors and BM25 index, then re-processes all files.
    """
    db = get_database()
    project = await db.projects.find_one({
        "_id": ObjectId(project_id), "owner_id": current_user.id
    })
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Clear existing indexes
    try:
        vector_db.delete_by_project(project_id)
        await bm25_service.remove_project(project_id)
    except Exception as e:
        log_error("reindex.clear", error=str(e))

    # Re-process all files
    files = await db.files.find({"project_id": project_id}).to_list(500)
    total_chunks = 0
    errors = []

    for file_doc in files:
        try:
            content = file_doc.get("content", "")
            filename = file_doc.get("filename", "unknown")
            chunks = await file_parser.parse_and_enrich(content, filename, project_id)
            if chunks:
                enriched_texts, raw_contents, metadatas, chunk_ids = zip(*chunks)
                vector_db.add_enriched_chunks(list(enriched_texts), list(metadatas), list(chunk_ids))
                await bm25_service.add_chunks(project_id, list(chunk_ids), list(raw_contents))
                total_chunks += len(chunks)
        except Exception as e:
            errors.append(f"{file_doc.get('filename')}: {str(e)}")

    return {
        "message": "Re-indexing complete",
        "files_processed": len(files),
        "total_chunks": total_chunks,
        "errors": errors[:10],
    }
