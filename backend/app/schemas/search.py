from pydantic import BaseModel
from typing import List, Optional

class SearchQuery(BaseModel):
    query: str
    project_id: Optional[str] = None
    top_k: int = 5

class SearchResult(BaseModel):
    id: str
    content: str
    metadata: dict
    score: float

class SearchResponse(BaseModel):
    results: List[SearchResult]
