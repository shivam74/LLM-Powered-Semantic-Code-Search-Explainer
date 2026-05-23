from fastapi import APIRouter, Depends, HTTPException
from typing import List
from bson import ObjectId

from app.api.dependencies import get_current_user
from app.schemas.user import UserResponse
from app.schemas.search import SearchQuery, SearchResponse, SearchResult
from app.db.database import get_database
from app.services.vector_db_service import vector_db

router = APIRouter()

@router.post("/", response_model=SearchResponse)
async def semantic_search(
    query: SearchQuery,
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    
    # Optional: Validate that the user owns the project if project_id is provided
    if query.project_id:
        project = await db.projects.find_one({
            "_id": ObjectId(query.project_id),
            "owner_id": current_user.id
        })
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")
            
    # Perform vector search
    # results is a List[Tuple[Document, float]]
    raw_results = vector_db.search(
        query=query.query,
        project_id=query.project_id,
        top_k=query.top_k
    )
    
    search_results = []
    for doc, score in raw_results:
        search_results.append(SearchResult(
            id=doc.metadata.get("filename", "unknown") + "_" + str(doc.metadata.get("chunk_index", 0)),
            content=doc.page_content,
            metadata=doc.metadata,
            score=float(score)
        ))
        
    return SearchResponse(results=search_results)
