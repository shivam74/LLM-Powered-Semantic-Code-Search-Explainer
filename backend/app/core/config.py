from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "LLM Semantic Code Search"
    
    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017/llm_code_search"
    
    # Security
    JWT_SECRET_KEY: str = "supersecretkey"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # AI Providers
    OPENAI_API_KEY: Optional[str] = None
    HUGGINGFACE_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # ── Hybrid Retrieval Settings ─────────────────────────────────────────
    # Weights for RRF-based score fusion (must sum to 1.0)
    VECTOR_WEIGHT: float = 0.7
    BM25_WEIGHT: float = 0.3

    # Number of candidates retrieved from each backend before fusion
    RETRIEVAL_CANDIDATE_K: int = 20

    # Final top-K results after fusion (and reranking if enabled)
    RETRIEVAL_TOP_K: int = 5

    # ── Reranker Settings ─────────────────────────────────────────────────
    # Set to true to enable cross-encoder reranking via HuggingFace API
    ENABLE_RERANKER: bool = False
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # ── Contextual Enrichment ─────────────────────────────────────────────
    # Rule-based enrichment is always on.
    # Set to true to additionally call the LLM to generate context summaries.
    ENABLE_LLM_ENRICHMENT: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
