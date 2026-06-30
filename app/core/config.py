from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # FastAPI
    API_TITLE: str = "RAG API"
    API_VERSION: str = "v1.0.0"
    API_DESCRIPTION: str = "Retrieval-Augmented Generation API with multi-user support"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite:///./rag_api.db"
    SQLALCHEMY_ECHO: bool = False

    # File Upload
    MAX_FILE_SIZE_MB: int = 50
    ASYNC_THRESHOLD_MB: int = 5
    ALLOWED_EXTENSIONS: str = "txt,md"  # Comma-separated
    TEMP_UPLOAD_DIR: str = "./temp_uploads"

    # RAG
    CHROMA_DB_PATH: str = "./chroma_db"
    KNOWLEDGE_BASE_PATH: str = "./knowledge_base"
    RAG_COMPONENTS_PATH: str = ""  # Path to local-rag-chromedb project (optional)
    MAX_CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # Embeddings
    EMBEDDINGS_MODEL: str = "nvidia/llama-nemotron-embed-vl-1b-v2"
    EMBEDDINGS_PROVIDER: str = "openrouter"  # openrouter or local
    OPENROUTER_API_KEY: str = ""
    DEVICE: str = "cpu"

    # Search
    DEFAULT_TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.5
    HYBRID_SEARCH_ALPHA: float = 0.5

    # Query Expansion
    QUERY_EXPANSION_ENABLED: bool = False
    QUERY_EXPANSION_NUM_VARIANTS: int = 3
    QUERY_EXPANSION_TIMEOUT: float = 5.0
    QUERY_EXPANSION_MODEL: str = "openai/gpt-4o-mini"

    # Security (MUST be set in production via env var)
    SECRET_KEY: str = ""
    API_KEY_PREFIX: str = "sk_rag_"
    API_KEY_LENGTH: int = 32

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8501"  # Comma-separated

    def __init__(self, **data):
        super().__init__(**data)
        # Validate SECRET_KEY in production
        if not self.DEBUG and not self.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set in production via environment variable")
        # Generate random SECRET_KEY if not set in development
        if not self.SECRET_KEY:
            import secrets
            self.SECRET_KEY = secrets.token_urlsafe(32)

    @property
    def allowed_extensions_list(self) -> list:
        """Get allowed extensions as list."""
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore unknown env vars


settings = Settings()
