from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List
from datetime import datetime
from bson import ObjectId

from app.api.dependencies import get_current_user
from app.schemas.user import UserResponse
from app.schemas.file import ProjectResponse, FileResponse
from app.db.database import get_database
from app.services.file_parser_service import file_parser
from app.services.vector_db_service import vector_db

router = APIRouter()

@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    name: str = Form(...),
    description: str = Form(None),
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    
    project_dict = {
        "name": name,
        "description": description,
        "owner_id": current_user.id,
        "created_at": datetime.utcnow()
    }
    
    result = await db.projects.insert_one(project_dict)
    
    return ProjectResponse(
        id=str(result.inserted_id),
        name=project_dict["name"],
        description=project_dict["description"],
        owner_id=project_dict["owner_id"],
        created_at=project_dict["created_at"]
    )

@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(current_user: UserResponse = Depends(get_current_user)):
    db = get_database()
    projects = await db.projects.find({"owner_id": current_user.id}).to_list(100)
    
    return [
        ProjectResponse(
            id=str(p["_id"]),
            name=p["name"],
            description=p.get("description"),
            owner_id=p["owner_id"],
            created_at=p["created_at"]
        ) for p in projects
    ]

@router.post("/upload/{project_id}")
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    
    # Verify project exists and belongs to user
    project = await db.projects.find_one({"_id": ObjectId(project_id), "owner_id": current_user.id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Read file content
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Only UTF-8 encoded text files are supported")
        
    # Parse and chunk the file
    documents = file_parser.parse_and_chunk(text_content, file.filename, project_id)
    
    # Add to Vector DB (ChromaDB)
    vector_db.add_documents(documents)
    
    # Save file metadata to MongoDB
    file_dict = {
        "filename": file.filename,
        "project_id": project_id,
        "owner_id": current_user.id,
        "content": text_content, # Storing full content for the editor view
        "created_at": datetime.utcnow()
    }
    
    result = await db.files.insert_one(file_dict)
    
    return {
        "id": str(result.inserted_id),
        "filename": file.filename,
        "chunks_processed": len(documents),
        "message": "File successfully uploaded and indexed"
    }

@router.get("/project/{project_id}/files")
async def list_project_files(
    project_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    files = await db.files.find({"project_id": project_id, "owner_id": current_user.id}).to_list(100)
    
    return [
        {
            "id": str(f["_id"]),
            "filename": f["filename"],
            "created_at": f["created_at"],
            "content": f["content"]
        } for f in files
    ]
