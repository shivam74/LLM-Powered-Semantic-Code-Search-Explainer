from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
from datetime import datetime
from bson import ObjectId
import os
import tempfile
import shutil
import subprocess
import asyncio

from app.api.dependencies import get_current_user
from app.schemas.user import UserResponse
from app.schemas.file import ProjectResponse, FileResponse
from app.db.database import get_database
from app.services.file_parser_service import file_parser
from app.services.vector_db_service import vector_db

router = APIRouter()

SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".cpp", ".c", ".h",
    ".java", ".go", ".rs", ".php", ".rb", ".swift", ".kt", ".cs",
    ".md", ".json", ".yaml", ".yml", ".toml", ".sh", ".bash",
}

class GithubImportRequest(BaseModel):
    repo_url: str


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


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()

    # Verify project exists and belongs to user
    project = await db.projects.find_one({"_id": ObjectId(project_id), "owner_id": current_user.id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete all vectors from ChromaDB for this project
    try:
        vector_db.delete_by_project(project_id)
    except Exception as e:
        print(f"Warning: could not delete vectors for project {project_id}: {e}")

    # Delete all files in the project from MongoDB
    await db.files.delete_many({"project_id": project_id})

    # Delete the project itself
    await db.projects.delete_one({"_id": ObjectId(project_id)})

    return {"message": "Project deleted successfully"}


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


@router.delete("/project/{project_id}/file/{file_id}")
async def delete_file(
    project_id: str,
    file_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()

    # Verify the file belongs to the user
    file_doc = await db.files.find_one({
        "_id": ObjectId(file_id),
        "project_id": project_id,
        "owner_id": current_user.id
    })
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete vectors from ChromaDB
    try:
        vector_db.delete_by_file(project_id, file_doc["filename"])
    except Exception as e:
        print(f"Warning: could not delete vectors for file {file_doc['filename']}: {e}")

    # Delete file record from MongoDB
    await db.files.delete_one({"_id": ObjectId(file_id)})

    return {"message": f"File '{file_doc['filename']}' deleted successfully"}


@router.post("/upload/github/{project_id}")
async def import_github_repo(
    project_id: str,
    body: GithubImportRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()

    # Verify project exists and belongs to user
    project = await db.projects.find_one({"_id": ObjectId(project_id), "owner_id": current_user.id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    repo_url = body.repo_url.strip()
    if not repo_url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only public GitHub HTTPS URLs are supported (e.g., https://github.com/owner/repo)")

    tmp_dir = tempfile.mkdtemp(prefix="git_clone_")
    try:
        # Run git clone in a thread-safe manner
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["git", "clone", "--depth=1", repo_url, tmp_dir],
                capture_output=True, text=True, timeout=120
            )
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to clone repository: {result.stderr.strip()}"
            )

        files_imported = 0
        files_skipped = 0
        errors = []

        # Walk through all files in the cloned repo
        for root, dirs, filenames in os.walk(tmp_dir):
            # Skip hidden directories (like .git)
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    files_skipped += 1
                    continue

                filepath = os.path.join(root, filename)
                # Use relative path from repo root as the display filename
                relative_path = os.path.relpath(filepath, tmp_dir).replace("\\", "/")

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        text_content = f.read()

                    if not text_content.strip():
                        files_skipped += 1
                        continue

                    # Cap very large files to avoid memory issues
                    if len(text_content) > 200_000:
                        text_content = text_content[:200_000]

                    # Parse and embed
                    documents = file_parser.parse_and_chunk(text_content, relative_path, project_id)
                    vector_db.add_documents(documents)

                    # Save to MongoDB
                    file_dict = {
                        "filename": relative_path,
                        "project_id": project_id,
                        "owner_id": current_user.id,
                        "content": text_content,
                        "created_at": datetime.utcnow()
                    }
                    await db.files.insert_one(file_dict)
                    files_imported += 1

                except Exception as e:
                    errors.append(f"{relative_path}: {str(e)}")
                    files_skipped += 1

    finally:
        # Always clean up the temp directory
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "message": f"Repository imported successfully",
        "files_imported": files_imported,
        "files_skipped": files_skipped,
        "errors": errors[:10]  # Only return first 10 errors to keep the response small
    }


@router.get("/project/{project_id}/files")
async def list_project_files(
    project_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    files = await db.files.find({"project_id": project_id, "owner_id": current_user.id}).to_list(500)
    
    return [
        {
            "id": str(f["_id"]),
            "filename": f["filename"],
            "created_at": f["created_at"],
            "content": f["content"]
        } for f in files
    ]
