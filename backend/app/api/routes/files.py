"""
Files route — updated to use the new AST + contextual enrichment indexing pipeline.
Existing API contract is fully preserved.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
from typing import List
from datetime import datetime
from bson import ObjectId
import os, tempfile, shutil, subprocess, asyncio

from app.api.dependencies import get_current_user
from app.schemas.user import UserResponse
from app.schemas.file import ProjectResponse, FileResponse
from app.db.database import get_database
from app.services.file_parser_service import file_parser
from app.services.vector_db_service import vector_db
from app.services.bm25_service import bm25_service
from app.services.observability import log_indexing_start, log_indexing_complete, log_error, Timer

router = APIRouter()

SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".cpp", ".c", ".h",
    ".java", ".go", ".rs", ".php", ".rb", ".swift", ".kt", ".cs",
    ".md", ".json", ".yaml", ".yml", ".toml", ".sh", ".bash",
}

class GithubImportRequest(BaseModel):
    repo_url: str


async def _index_file(content: str, filename: str, project_id: str, owner_id: str, db):
    """
    Core indexing function used by both file upload and GitHub import.
    Returns the number of chunks processed.
    """
    log_indexing_start(project_id, filename)
    with Timer() as t:
        # Parse and enrich with new pipeline
        chunks = await file_parser.parse_and_enrich(content, filename, project_id)

        if not chunks:
            return 0

        enriched_texts, raw_contents, metadatas, chunk_ids = zip(*chunks)

        # Index into ChromaDB (embeddings from enriched text)
        vector_db.add_enriched_chunks(
            enriched_texts=list(enriched_texts),
            metadatas=list(metadatas),
            ids=list(chunk_ids),
        )

        # Index into BM25 (raw text for keyword matching)
        await bm25_service.add_chunks(
            project_id=project_id,
            chunk_ids=list(chunk_ids),
            raw_contents=list(raw_contents),
        )

    log_indexing_complete(project_id, filename, len(chunks), t.elapsed_ms)
    return len(chunks)


# ── Project endpoints ─────────────────────────────────────────────────────────

@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    name: str = Form(...),
    description: str = Form(None),
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    project_dict = {
        "name": name, "description": description,
        "owner_id": current_user.id, "created_at": datetime.utcnow()
    }
    result = await db.projects.insert_one(project_dict)
    return ProjectResponse(
        id=str(result.inserted_id), name=project_dict["name"],
        description=project_dict["description"], owner_id=project_dict["owner_id"],
        created_at=project_dict["created_at"]
    )


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(current_user: UserResponse = Depends(get_current_user)):
    db = get_database()
    projects = await db.projects.find({"owner_id": current_user.id}).to_list(100)
    return [
        ProjectResponse(
            id=str(p["_id"]), name=p["name"], description=p.get("description"),
            owner_id=p["owner_id"], created_at=p["created_at"]
        ) for p in projects
    ]


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    project = await db.projects.find_one({"_id": ObjectId(project_id), "owner_id": current_user.id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        vector_db.delete_by_project(project_id)
        await bm25_service.remove_project(project_id)
    except Exception as e:
        log_error("delete_project", error=str(e))
    await db.files.delete_many({"project_id": project_id})
    await db.projects.delete_one({"_id": ObjectId(project_id)})
    return {"message": "Project deleted successfully"}


# ── File endpoints ────────────────────────────────────────────────────────────

@router.post("/upload/{project_id}")
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    project = await db.projects.find_one({"_id": ObjectId(project_id), "owner_id": current_user.id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Only UTF-8 encoded text files are supported")

    chunks_processed = await _index_file(text_content, file.filename, project_id, current_user.id, db)

    file_dict = {
        "filename": file.filename, "project_id": project_id,
        "owner_id": current_user.id, "content": text_content,
        "created_at": datetime.utcnow()
    }
    result = await db.files.insert_one(file_dict)

    return {
        "id": str(result.inserted_id), "filename": file.filename,
        "chunks_processed": chunks_processed,
        "message": "File successfully uploaded and indexed"
    }


@router.delete("/project/{project_id}/file/{file_id}")
async def delete_file(
    project_id: str, file_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    file_doc = await db.files.find_one({
        "_id": ObjectId(file_id), "project_id": project_id, "owner_id": current_user.id
    })
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        vector_db.delete_by_file(project_id, file_doc["filename"])
        await bm25_service.remove_by_filename(project_id, file_doc["filename"])
    except Exception as e:
        log_error("delete_file", error=str(e))
    await db.files.delete_one({"_id": ObjectId(file_id)})
    return {"message": f"File '{file_doc['filename']}' deleted successfully"}


@router.get("/project/{project_id}/files")
async def list_project_files(
    project_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    files = await db.files.find({"project_id": project_id, "owner_id": current_user.id}).to_list(500)
    return [
        {"id": str(f["_id"]), "filename": f["filename"],
         "created_at": f["created_at"], "content": f["content"]}
        for f in files
    ]


# ── GitHub import ─────────────────────────────────────────────────────────────

@router.post("/upload/github/{project_id}")
async def import_github_repo(
    project_id: str,
    body: GithubImportRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    project = await db.projects.find_one({"_id": ObjectId(project_id), "owner_id": current_user.id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    repo_url = body.repo_url.strip()
    if not repo_url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only public GitHub HTTPS URLs are supported")

    tmp_dir = tempfile.mkdtemp(prefix="git_clone_")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["git", "clone", "--depth=1", repo_url, tmp_dir],
                capture_output=True, text=True, timeout=120
            )
        )
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=f"Failed to clone: {result.stderr.strip()}")

        files_imported = 0
        files_skipped = 0
        errors = []

        for root, dirs, filenames in os.walk(tmp_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    files_skipped += 1
                    continue
                filepath = os.path.join(root, filename)
                relative_path = os.path.relpath(filepath, tmp_dir).replace("\\", "/")
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        text_content = f.read()
                    if not text_content.strip():
                        files_skipped += 1
                        continue
                    if len(text_content) > 200_000:
                        text_content = text_content[:200_000]

                    chunks_n = await _index_file(text_content, relative_path, project_id, current_user.id, db)

                    file_dict = {
                        "filename": relative_path, "project_id": project_id,
                        "owner_id": current_user.id, "content": text_content,
                        "created_at": datetime.utcnow()
                    }
                    await db.files.insert_one(file_dict)
                    files_imported += 1
                except Exception as e:
                    errors.append(f"{relative_path}: {str(e)}")
                    files_skipped += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "message": "Repository imported successfully",
        "files_imported": files_imported,
        "files_skipped": files_skipped,
        "errors": errors[:10]
    }
