from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: str
    owner_id: str
    created_at: datetime
    
class FileBase(BaseModel):
    filename: str
    project_id: str
    file_path: str

class FileResponse(FileBase):
    id: str
    created_at: datetime
