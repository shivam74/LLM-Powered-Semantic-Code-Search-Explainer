from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db.database import connect_to_mongo, close_mongo_connection

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()

app = FastAPI(
    title="Semantic Code Search & AI Code Explainer API",
    description="API for uploading code, performing semantic search, and getting AI explanations.",
    version="1.0.0",
    lifespan=lifespan
)

from app.api.routes import auth, files, search, chat

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(files.router, prefix="/api/files", tags=["Files & Projects"])
app.include_router(search.router, prefix="/api/search", tags=["Semantic Search"])
app.include_router(chat.router, prefix="/api/chat", tags=["AI Chat"])

@app.get("/")
async def root():
    return {"message": "Welcome to the Semantic Code Search API"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
