from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


# Auth Schemas
class UserRegister(BaseModel):
    username: str
    email: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyResponse(BaseModel):
    api_key: str


class APIKeyListItem(BaseModel):
    id: str
    key_hash: str  # Show hash prefix for identification, not the actual key
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyListResponse(BaseModel):
    keys: List[APIKeyListItem]
    total: int


# Collection Schemas
class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class CollectionListResponse(BaseModel):
    collections: List[CollectionResponse]
    total: int
    offset: int = 0
    limit: int = 50


# Document Schemas
class DocumentResponse(BaseModel):
    id: str
    collection_id: str
    filename: str
    file_size: int
    chunks_count: int
    status: str
    indexed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    offset: int = 0
    limit: int = 50


class ChunkResponse(BaseModel):
    id: str
    content: str
    chunk_index: int
    metadata: Optional[dict] = None


class DocumentChunksResponse(BaseModel):
    document_id: str
    filename: str
    chunks: List[ChunkResponse]
    total_chunks: int


# Upload Schemas
class DocumentUploadResponse(BaseModel):
    status: str
    document_id: str
    filename: str
    file_size: int
    chunks_created: int
    indexed_at: datetime


class AsyncUploadResponse(BaseModel):
    status: str
    session_id: str
    filename: str
    file_size: int
    estimated_time_seconds: Optional[int] = None
    status_url: str


class UploadSessionStatus(BaseModel):
    session_id: str
    status: str
    progress_percent: int
    current_chunk: Optional[int] = None
    total_chunks: Optional[int] = None
    elapsed_seconds: int
    estimated_remaining_seconds: Optional[int] = None
    error: Optional[str] = None


class UploadSessionCompleted(BaseModel):
    session_id: str
    status: str
    document_id: str
    chunks_created: int
    completed_at: datetime


# Search Schemas
class SearchRequest(BaseModel):
    query: str
    collection_id: str = "default"
    top_k: Optional[int] = 5
    threshold: Optional[float] = 0.5
    use_hybrid: Optional[bool] = True
    use_query_expansion: Optional[bool] = None
    # Optional filters
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    service_name: Optional[str] = None
    environment: Optional[str] = None
    team: Optional[str] = None
    tags: Optional[List[str]] = None
    chunk_type: Optional[str] = None
    chunk_language: Optional[str] = None
    severity: Optional[str] = None


class SearchResultItem(BaseModel):
    content: str
    source: str
    score: float
    metadata: Optional[dict] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]
    search_time_ms: float
    result_count: int


class BatchSearchRequest(BaseModel):
    queries: List[str]
    collection_id: str = "default"
    top_k: Optional[int] = 5
    threshold: Optional[float] = 0.5
    use_hybrid: Optional[bool] = True
    use_query_expansion: Optional[bool] = None
    # Optional filters
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    service_name: Optional[str] = None
    environment: Optional[str] = None
    team: Optional[str] = None
    tags: Optional[List[str]] = None
    chunk_type: Optional[str] = None
    chunk_language: Optional[str] = None
    severity: Optional[str] = None


class BatchSearchResponse(BaseModel):
    results: List[SearchResponse]
    total_queries: int
    total_time_ms: float


class SuggestResponse(BaseModel):
    query: str
    suggestions: List[str]
    suggestion_count: int


# Stats and Content Schemas
class CollectionStatsResponse(BaseModel):
    collection_id: str
    document_count: int
    total_chunks: int
    total_size_bytes: int
    status_counts: dict  # {status: count}
    last_indexed_at: Optional[datetime] = None
    created_at: datetime


class DocumentContentResponse(BaseModel):
    document_id: str
    filename: str
    content: str
    char_count: int


class DocumentReindexResponse(BaseModel):
    document_id: str
    chunks_created: int
    indexed_at: datetime


# Health Schemas
class HealthResponse(BaseModel):
    status: str
    version: str
    embeddings_model: str
    vector_store: str
    database: str
    uptime_seconds: int


# Error Schemas
class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
