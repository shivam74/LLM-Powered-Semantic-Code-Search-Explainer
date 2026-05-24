from pydantic import BaseModel
from typing import List, Optional

class SearchQuery(BaseModel):
    query: str
    project_id: Optional[str] = None
    top_k: int = 5

class SearchResult(BaseModel):
    id: str
    content: str        # raw code shown to user
    metadata: dict      # includes filename, language, function_name, etc.
    score: float        # fusion score (or vector score for legacy compat)
    # Extended fields (optional — older frontends ignore unknown fields)
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None

class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int = 0
