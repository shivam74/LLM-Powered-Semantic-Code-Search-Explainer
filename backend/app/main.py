from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db.database import connect_to_mongo, close_mongo_connection

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(
    title="Semantic Code Search & AI Code Explainer API",
    description="Production-grade contextual retrieval: AST chunking, hybrid BM25+vector search, reranking.",
    version="2.0.0",
    lifespan=lifespan
)

from app.api.routes import auth, files, search, chat, retrieval

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/api/auth",      tags=["Authentication"])
app.include_router(files.router,     prefix="/api/files",     tags=["Files & Projects"])
app.include_router(search.router,    prefix="/api/search",    tags=["Semantic Search"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["AI Chat"])
app.include_router(retrieval.router, prefix="/api/retrieval", tags=["Retrieval Debug"])

@app.get("/")
async def root():
    return {"message": "Semantic Code Search API v2.0 — Contextual Retrieval"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}
