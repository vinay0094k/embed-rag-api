from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import os

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


def _load_env_file():
    """Load .env file into environment variables."""
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())


_load_env_file()


class AppConfig(BaseSettings):
    name: str = "local-rag-chromedb"
    log_level: str = "INFO"
    log_dir: str = "./logs"


class ChromaConfig(BaseSettings):
    persist_dir: str = "./chroma_db"
    collection_name: str = "rag_documents"
    distance_metric: str = "cosine"
    hnsw_space: str = "cosine"
    hnsw_construction_ef: int = 200
    hnsw_search_ef: int = 100


class EmbeddingsConfig(BaseSettings):
    provider: str = "chroma_default"
    model: str = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
    openrouter_api_key: Optional[str] = None
    dimension: int = 4096
    endpoint: Optional[str] = None
    batch_size: int = 100
    max_retries: int = 3
    timeout_seconds: int = 60


class LLMModelEntry(BaseModel):
    """A single named LLM model that can be selected at query time."""
    display_name: str = ""
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class LLMConfig(BaseSettings):
    # Shared generation settings (apply to all models)
    temperature: float = 0.1
    max_tokens: int = 2048
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    streaming: bool = True
    max_retries: int = 3
    timeout_seconds: int = 60
    system_prompt: str = (
        "You are a RAG-AI assistant. Answer questions using ONLY the provided context.\n"
        "After every factual statement cite its source using [S1], [S2], [S3] etc.\n"
        "The citation IDs match the [S1], [S2] labels at the start of each context block.\n"
        "If context is insufficient, say \"I don't have enough information to answer.\""
    )

    # Named model registry — add as many as needed
    active_model: str = "model1"
    models: Dict[str, LLMModelEntry] = Field(default_factory=lambda: {
        "model1": LLMModelEntry(
            display_name="DeepSeek V4 Flash",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com/v1",
        )
    })

    # Legacy single-model fields kept for backward compat — used if models dict is empty
    model: str = "deepseek-v4-flash"
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    def get_model_entry(self, model_id: Optional[str] = None) -> LLMModelEntry:
        """Return the LLMModelEntry for model_id (or active_model if not specified)."""
        mid = model_id or self.active_model
        if mid in self.models:
            return self.models[mid]
        # Fallback to legacy fields
        return LLMModelEntry(model=self.model, base_url=self.base_url, api_key=self.api_key)


class ChunkingDefaultsConfig(BaseSettings):
    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_size: int = 100


class CodeChunkConfig(BaseSettings):
    chunk_size: int = 1500
    chunk_overlap: int = 100
    languages: List[str] = [
        "python", "javascript", "typescript", "go", "rust",
        "java", "bash", "dockerfile", "hcl", "terraform",
    ]


class YAMLChunkConfig(BaseSettings):
    max_depth: int = 3
    preserve_keys: bool = True
    split_on_top_level: bool = True


class JSONChunkConfig(BaseSettings):
    max_array_items: int = 50
    split_on_array: bool = True


class LogsChunkConfig(BaseSettings):
    chunk_size: int = 2000
    chunk_overlap: int = 200
    timestamp_pattern: str = r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
    split_on_timestamp: bool = True


class MarkdownCodeChunkConfig(BaseSettings):
    chunk_size: int = 1500
    chunk_overlap: int = 100
    headers_to_split_on: List[Tuple[str, str]] = [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ]
    preserve_code_fences: bool = True


class ByTypeChunkingConfig(BaseSettings):
    code: CodeChunkConfig = Field(default_factory=CodeChunkConfig)
    yaml: YAMLChunkConfig = Field(default_factory=YAMLChunkConfig)
    json_config: JSONChunkConfig = Field(default_factory=JSONChunkConfig)
    logs: LogsChunkConfig = Field(default_factory=LogsChunkConfig)
    markdown_code: MarkdownCodeChunkConfig = Field(default_factory=MarkdownCodeChunkConfig)


class ChunkingConfig(BaseSettings):
    default: ChunkingDefaultsConfig = Field(default_factory=ChunkingDefaultsConfig)
    by_type: ByTypeChunkingConfig = Field(default_factory=ByTypeChunkingConfig)


class TagPattern(BaseSettings):
    name: str
    pattern: str


class ExtractionConfig(BaseSettings):
    service_name_patterns: List[str] = [
        "services/(?P<service>[^/]+)",
        "apps/(?P<service>[^/]+)",
        "(?P<service>[^/]+)/deployment",
        "(?P<service>[^/]+)/manifests",
        "(?P<service>[^/]+)/Dockerfile",
        "(?P<service>[^/]+)/values\\.yaml",
        "(?P<service>[^/]+)/main\\.tf",
    ]
    environment_patterns: List[str] = [
        "environments/(?P<env>[^/]+)",
        "envs/(?P<env>[^/]+)",
        "/(?P<env>production|staging|dev|test|local|prod)/",
    ]
    team_patterns: List[str] = [
        "teams/(?P<team>[^/]+)",
        "owned-by/(?P<team>[^/]+)",
        "team-(?P<team>[^/]+)",
    ]
    source_type_mapping: Dict[str, str] = {
        ".yaml": "kubernetes",
        ".yml": "kubernetes",
        ".tf": "terraform",
        ".tfvars": "terraform",
        ".hcl": "terraform",
        "Dockerfile": "dockerfile",
        ".dockerfile": "dockerfile",
        ".sh": "bash",
        ".bash": "bash",
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".log": "logs",
        ".md": "runbook",
        ".txt": "runbook",
        ".json": "json",
    }


class MetadataConfig(BaseSettings):
    required_fields: List[str] = [
        "source_path", "source_name", "source_type",
        "indexed_at", "doc_modified_at",
    ]
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    tag_patterns: List[TagPattern] = Field(default_factory=lambda: [
        TagPattern(name="deployment", pattern=r"(?i)(deployment|deploy|rollout)"),
        TagPattern(name="canary", pattern=r"(?i)canary"),
        TagPattern(name="rollback", pattern=r"(?i)rollback"),
        TagPattern(name="incident", pattern=r"(?i)(incident|outage|postmortem|rca)"),
        TagPattern(name="security", pattern=r"(?i)(security|vulnerability|cve|secret|credential)"),
        TagPattern(name="scaling", pattern=r"(?i)(autoscal|hpa|vpa|replica)"),
        TagPattern(name="networking", pattern=r"(?i)(ingress|service|networkpolicy|dns)"),
        TagPattern(name="storage", pattern=r"(?i)(pv|pvc|storageclass|volume)"),
    ])
    filterable_fields: List[str] = [
        "source_type", "service_name", "environment", "team",
        "tags", "chunk_type", "chunk_language", "severity",
    ]
    date_fields: List[str] = [
        "indexed_at", "doc_modified_at", "doc_created_at",
    ]
    display_fields: List[str] = [
        "source_name", "service_name", "environment",
        "chunk_symbol", "doc_modified_at",
    ]


class BM25Config(BaseSettings):
    k1: float = 1.5
    b: float = 0.75
    index_path: str = "./chroma_db/bm25_index.pkl"


class HybridRetrievalConfig(BaseSettings):
    top_k: int = 10  # Reduced from 20 for faster retrieval (fewer candidates to process)
    final_top_k: int = 5
    search_type: str = "mmr"
    mmr_lambda: float = 0.5


class HybridSearchConfig(BaseSettings):
    enabled: bool = True
    vector_weight: float = 0.7
    bm25_weight: float = 0.3
    fusion_method: str = "rrf"
    rrf_k: int = 60
    bm25: BM25Config = Field(default_factory=BM25Config)
    retrieval: HybridRetrievalConfig = Field(default_factory=HybridRetrievalConfig)


class RetrievalConfig(BaseSettings):
    top_k: int = 5
    search_type: str = "mmr"
    mmr_lambda: float = 0.5
    score_threshold: float = 0.0
    max_context_tokens: int = 8000
    max_candidates_per_source: int = 5  # pre-rerank cap; 0 = no limit
    max_chunks_per_source: int = 3       # post-rerank cap; 0 = no limit
    context_template: str = (
        "[Source: {source_name} | Service: {service_name} | "
        "Env: {environment} | Type: {chunk_type} | Symbol: {chunk_symbol}]\n"
        "{content}"
    )


class RerankerConfig(BaseSettings):
    enabled: bool = True
    provider: str = "local"  # "local" or "openrouter"
    model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    base_url: str = "https://openrouter.ai/api/v1/rerank"
    top_n: int = 5
    cache_ttl_seconds: int = 900  # 15 minutes; 0 disables cache


class QueryExpansionConfig(BaseSettings):
    enabled: bool = False
    num_variants: int = 3  # extra queries generated (original is always included)
    timeout_seconds: float = 5.0  # max wait for LLM expansion before falling back


class ContextCompressionConfig(BaseSettings):
    enabled: bool = False
    # Compressed excerpts shorter than this fall back to the original chunk
    min_chars: int = 80


class GroundingConfig(BaseSettings):
    enabled: bool = False
    timeout_seconds: float = 10.0


class EvaluationConfig(BaseSettings):
    test_set_path: str = "./eval/test_cases.jsonl"
    metrics: List[str] = [
        "hit_rate@1", "hit_rate@3", "hit_rate@5",
        "mrr@5", "mrr@10", "precision@5", "answer_f1",
    ]
    answer_similarity_threshold: float = 0.8


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RAG_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app: AppConfig = Field(default_factory=AppConfig)
    chroma: ChromaConfig = Field(default_factory=ChromaConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    hybrid_search: HybridSearchConfig = Field(default_factory=HybridSearchConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    query_expansion: QueryExpansionConfig = Field(default_factory=QueryExpansionConfig)
    context_compression: ContextCompressionConfig = Field(default_factory=ContextCompressionConfig)
    grounding: GroundingConfig = Field(default_factory=GroundingConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)


def load_config(config_path: str = "config.yaml") -> Settings:
    path = Path(config_path)
    if not path.exists():
        return Settings()

    with open(path) as f:
        raw = yaml.safe_load(f)
    return Settings(**raw)
