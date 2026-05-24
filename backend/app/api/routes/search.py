from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.api.dependencies import get_current_user
from app.schemas.user import UserResponse
from app.schemas.search import SearchQuery, SearchResponse, SearchResult
from app.db.database import get_database
from app.services.hybrid_retrieval_service import hybrid_retrieval

router = APIRouter()

@router.post("/", response_model=SearchResponse)
async def semantic_search(
    query: SearchQuery,
    current_user: UserResponse = Depends(get_current_user),
):
    db = get_database()

    if query.project_id:
        project = await db.projects.find_one({
            "_id": ObjectId(query.project_id),
            "owner_id": current_user.id,
        })
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")

    # Hybrid retrieval: vector + BM25 + optional rerank
    results = await hybrid_retrieval.search(
        query=query.query,
        project_id=query.project_id,
        top_k=query.top_k,
    )

    search_results = [
        SearchResult(
            id=r.chunk_id,
            content=r.raw_content,
            metadata=r.metadata,
            score=round(r.fusion_score, 6),
            vector_score=round(r.vector_score, 6),
            bm25_score=round(r.bm25_score, 6),
        )
        for r in results
    ]

    return SearchResponse(results=search_results, total=len(search_results))
