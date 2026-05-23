from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "LLM Semantic Code Search"
    
    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017/llm_code_search"
    
    # Security
    JWT_SECRET_KEY: str = "supersecretkey" # Override in production
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # AI Providers
    OPENAI_API_KEY: Optional[str] = None
    HUGGINGFACE_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()
