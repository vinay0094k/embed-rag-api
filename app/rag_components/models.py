from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    CODE = "code"
    YAML = "yaml"
    JSON = "json"
    LOGS = "logs"
    MARKDOWN_CODE = "markdown_code"
    GENERIC = "generic"


class SourceType(str, Enum):
    KUBERNETES = "kubernetes"
    TERRAFORM = "terraform"
    DOCKERFILE = "dockerfile"
    HELM = "helm"
    CI_CD = "ci-cd"
    LOGS = "logs"
    RUNBOOK = "runbook"
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    BASH = "bash"
    JSON = "json"
    CONFIG = "config"
    UNKNOWN = "unknown"


class ChunkType(str, Enum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    YAML_KEY = "yaml_key"
    JSON_OBJECT = "json_object"
    JSON_ARRAY_ITEM = "json_array_item"
    LOG_BLOCK = "log_block"
    SECTION = "section"
    MARKDOWN_SECTION = "markdown_section"
    CODE_BLOCK = "code_block"


class ChunkMetadata(BaseModel):
    source_path: str
    source_name: str
    source_type: str

    document_id: str = ""  # For collection-scoped deletion
    collection_id: str = ""  # For collection-scoped deletion

    service_name: Optional[str] = None
    service_version: Optional[str] = None
    environment: Optional[str] = None
    team: Optional[str] = None

    indexed_at: str = ""
    doc_modified_at: str = ""
    doc_created_at: Optional[str] = None

    chunk_type: str = ChunkType.SECTION.value
    chunk_symbol: Optional[str] = None
    chunk_language: Optional[str] = None
    chunk_index: int = 0
    total_chunks: int = 1

    tags: List[str] = Field(default_factory=list)
    severity: Optional[str] = None

    model_config = {"extra": "allow", "populate_by_name": True}


class DocumentChunk(BaseModel):
    id: str
    content: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None


class MetadataFilter(BaseModel):
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    service_name: Optional[str] = None
    environment: Optional[str] = None
    team: Optional[str] = None
    tags: Optional[List[str]] = None
    chunk_type: Optional[str] = None
    chunk_language: Optional[str] = None
    severity: Optional[str] = None
    source_path_prefix: Optional[str] = None
    indexed_at_since: Optional[str] = None
    indexed_at_until: Optional[str] = None
    doc_modified_at_since: Optional[str] = None
    doc_modified_at_until: Optional[str] = None

    def to_chroma_where(self) -> Dict[str, Any]:
        conditions = []
        exact_fields = {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "service_name": self.service_name,
            "environment": self.environment,
            "team": self.team,
            "chunk_type": self.chunk_type,
            "chunk_language": self.chunk_language,
            "severity": self.severity,
        }
        for field, value in exact_fields.items():
            if value is not None:
                conditions.append({field: {"$eq": value}})

        if self.tags:
            conditions.append({"tags": {"$in": self.tags}})

        date_pairs = [
            ("indexed_at", self.indexed_at_since, self.indexed_at_until),
            ("doc_modified_at", self.doc_modified_at_since, self.doc_modified_at_until),
        ]
        for field, since, until in date_pairs:
            if since:
                conditions.append({field: {"$gte": since}})
            if until:
                conditions.append({field: {"$lte": until}})

        if not conditions:
            return {}
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def matches_source_path_prefix(self, source_path: str) -> bool:
        """Check if source_path matches the prefix filter (done in Python, not in ChromaDB)."""
        if not self.source_path_prefix:
            return True
        return source_path.startswith(self.source_path_prefix)


class RawDocument(BaseModel):
    file_path: str
    file_name: str
    file_extension: str
    content: str
    file_size: int
    doc_modified_at: str
    doc_created_at: Optional[str] = None


class RetrievalResult(BaseModel):
    chunk: DocumentChunk
    score: float
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None
    fused_score: Optional[float] = None


class QueryRequest(BaseModel):
    query: str
    filters: Optional[MetadataFilter] = None
    top_k: int = 5
    search_type: str = "hybrid"
    stream: bool = True
    score_threshold: float = 0.0
    history: List[Dict[str, str]] = Field(default_factory=list)


class QueryResponse(BaseModel):
    answer: str
    sources: List[RetrievalResult]
    query: str
    filters_applied: Optional[MetadataFilter] = None
    retrieval_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    total_tokens: int = 0


class TestCase(BaseModel):
    id: str
    question: str
    ground_truth_document_id: str
    expected_answer_snippet: str
    filters: Optional[MetadataFilter] = None
    category: Optional[str] = None


class EvaluationResult(BaseModel):
    test_case_id: str
    question: str
    retrieved_doc_ids: List[str]
    hit_at_k: Dict[str, bool]
    mrr: float
    answer: str = ""
    answer_f1: float = 0.0
    latency_ms: float = 0.0


class PerCategoryMetrics(BaseModel):
    hit_rate_at_1: float = 0.0
    hit_rate_at_3: float = 0.0
    hit_rate_at_5: float = 0.0
    mrr: float = 0.0
    count: int = 0


class EvaluationSummary(BaseModel):
    total_cases: int = 0
    hit_rate_at_1: float = 0.0
    hit_rate_at_3: float = 0.0
    hit_rate_at_5: float = 0.0
    hit_rate_at_10: float = 0.0
    mrr_at_5: float = 0.0
    mrr_at_10: float = 0.0
    precision_at_5: float = 0.0
    avg_answer_f1: float = 0.0
    avg_latency_ms: float = 0.0
    per_category: Dict[str, Dict[str, float]] = Field(default_factory=dict)
