from pydantic import BaseModel
from typing import Optional
from enum import Enum

class ChatAction(str, Enum):
    EXPLAIN = "explain"
    DETECT_BUGS = "detect_bugs"
    OPTIMIZE = "optimize"
    GENERAL = "general"

class ChatRequest(BaseModel):
    action: ChatAction
    code: Optional[str] = ""
    query: Optional[str] = ""
    project_id: Optional[str] = None
    
class ChatResponse(BaseModel):
    response: str
