from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChunkMetadata(BaseModel):
    chunk_id: str
    filename: str
    language: str
    chunk_type: str
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    imports: Optional[str] = None

class DebugSearchQuery(BaseModel):
    query: str
    project_id: str
    top_k: int = 20    # return all candidates for debug

class DebugSearchResult(BaseModel):
    chunk_id: str
    raw_content: str
    metadata: Dict[str, Any]
    vector_score: float
    bm25_score: float
    fusion_score: float

class DebugSearchResponse(BaseModel):
    query: str
    results: List[DebugSearchResult]
    total_candidates: int

class ProjectStats(BaseModel):
    project_id: str
    total_chunks: int
    bm25_indexed: int
    languages: List[str]
    files: List[str]
