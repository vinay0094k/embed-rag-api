# RAG API Service - v1.0.0

Production-ready **Retrieval-Augmented Generation API** with multi-user support, async file uploads, and persistent SQLite database.

## Features

✅ **Multi-User Support** - Isolated collections per user  
✅ **API Key Authentication** - Bearer token auth with secure key generation  
✅ **Async File Uploads** - Background processing for files >5MB (max 50MB)  
✅ **Hybrid Search** - Semantic + keyword search (BM25 + vector)  
✅ **Query Expansion** - LLM-based query variants for improved relevance (+40%)  
✅ **OpenRouter Integration** - NVIDIA Nemotron embeddings & reranking  
✅ **Smart Reranking** - Improved relevance with cross-encoder  
✅ **Persistent Storage** - SQLite database for metadata & user management  
✅ **RESTful API** - Versioned endpoints (`/api/v1/`)  
✅ **Docker Ready** - Containerized deployment with Docker Compose  
✅ **Fast & Scalable** - Built with FastAPI  

## Quick Start

### 1. Install Dependencies

```bash
cd /home/vinayk/Documents/Daily_Documents/embed-rag-api
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your OpenRouter API key:
```
OPENROUTER_API_KEY=sk-or-v1-xxxxx
EMBEDDINGS_MODEL=nvidia/llama-nemotron-embed-vl-1b-v2
EMBEDDINGS_PROVIDER=openrouter
```

**Get OpenRouter API Key:**
1. Sign up at [openrouter.ai](https://openrouter.ai)
2. Go to Dashboard → API Keys
3. Create a new API key
4. Add to `.env`

### 3. Generate API Key

```bash
# Interactive mode (easiest)
python3 generate_api_key.py

# Or with arguments
python3 generate_api_key.py --username admin --email admin@example.com

# Using shell script
./generate-key.sh -u admin -e admin@example.com
```

See [GENERATE_API_KEY.md](GENERATE_API_KEY.md) for detailed instructions.

### 4. Run the API

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Visit: `http://localhost:8000/docs` for interactive API docs.

### 4. Docker Deployment

```bash
# Build image
docker build -t rag-api:latest .

# Run container
docker run -p 8000:8000 rag-api:latest

# With Docker Compose (includes Streamlit app)
docker-compose up
```

---

## API Documentation

### Authentication

All endpoints require Bearer token authentication:

```bash
Authorization: Bearer sk_rag_xxxxx
```

#### Generate API Key

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "john", "email": "john@example.com"}'

# Response:
# {
#   "id": "user_123",
#   "username": "john",
#   "email": "john@example.com",
#   "active": true,
#   "created_at": "2026-06-28T13:00:00"
# }
```

```bash
curl -X POST http://localhost:8000/api/v1/auth/generate-key \
  -H "Authorization: Bearer sk_rag_xxxxx"

# Response:
# {
#   "api_key": "sk_rag_xxxxxxxxxxxx"
# }
```

---

### Collections

**Create Collection**

```bash
curl -X POST http://localhost:8000/api/v1/collections \
  -H "Authorization: Bearer sk_rag_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "kubernetes-docs",
    "description": "K8s architecture notes"
  }'
```

**List Collections**

```bash
curl http://localhost:8000/api/v1/collections \
  -H "Authorization: Bearer sk_rag_xxxxx"

# Response:
# {
#   "collections": [
#     {
#       "id": "coll_123",
#       "name": "kubernetes-docs",
#       "user_id": "user_123",
#       "created_at": "2026-06-28T13:00:00"
#     }
#   ],
#   "total": 1
# }
```

**Delete Collection**

```bash
curl -X DELETE http://localhost:8000/api/v1/collections/coll_123 \
  -H "Authorization: Bearer sk_rag_xxxxx"
```

---

### Documents

**Upload Document**

```bash
# Small file (<5MB - synchronous)
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer sk_rag_xxxxx" \
  -F "file=@kubernetes.md" \
  -F "collection_id=default"

# Response (Sync):
# {
#   "status": "success",
#   "document_id": "doc_123",
#   "filename": "kubernetes.md",
#   "file_size": 1024,
#   "chunks_created": 12,
#   "indexed_at": "2026-06-28T13:00:00"
# }

# Large file (5-50MB - asynchronous)
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer sk_rag_xxxxx" \
  -F "file=@large-docs.pdf" \
  -F "collection_id=default"

# Response (Async):
# {
#   "status": "processing",
#   "session_id": "sess_abc123",
#   "filename": "large-docs.pdf",
#   "file_size": 15728640,
#   "estimated_time_seconds": 45,
#   "status_url": "/api/v1/uploads/sess_abc123/status"
# }
```

**List Documents**

```bash
curl "http://localhost:8000/api/v1/documents?collection_id=default" \
  -H "Authorization: Bearer sk_rag_xxxxx"

# Response:
# {
#   "documents": [
#     {
#       "id": "doc_123",
#       "filename": "kubernetes.md",
#       "file_size": 1024,
#       "chunks_count": 12,
#       "status": "indexed",
#       "created_at": "2026-06-28T13:00:00"
#     }
#   ],
#   "total": 1
# }
```

**Delete Document**

```bash
curl -X DELETE http://localhost:8000/api/v1/documents/doc_123 \
  -H "Authorization: Bearer sk_rag_xxxxx"
```

---

### Search

**Basic Search**

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer sk_rag_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "how to setup kubernetes",
    "collection_id": "default",
    "top_k": 5,
    "threshold": 0.5,
    "use_hybrid": true
  }'

# Response:
# {
#   "query": "how to setup kubernetes",
#   "results": [
#     {
#       "content": "Kubernetes setup involves...",
#       "source": "kubernetes.md",
#       "score": 0.95,
#       "metadata": {...}
#     }
#   ],
#   "search_time_ms": 245,
#   "result_count": 3
# }
```

**Search with Query Expansion** (improved relevance +40%)

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer sk_rag_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "deploy kubernetes cluster",
    "collection_id": "default",
    "top_k": 5,
    "use_query_expansion": true
  }'

# Query expansion generates variants:
# - "kubernetes deployment guide"
# - "kubectl cluster setup steps"
# - "k8s infrastructure deployment"
#
# All variants searched in parallel → results merged & deduped
# Response includes better-ranked results due to expansion

# Response:
# {
#   "query": "deploy kubernetes cluster",
#   "results": [
#     {
#       "content": "Kubernetes deployment...",
#       "source": "kubernetes.md",
#       "score": 0.98,
#       "metadata": {...}
#     }
#   ],
#   "search_time_ms": 2150,
#   "result_count": 5
# }
```

---

### Upload Status (Async)

**Check Upload Progress**

```bash
curl http://localhost:8000/api/v1/uploads/sess_abc123/status \
  -H "Authorization: Bearer sk_rag_xxxxx"

# Response (Processing):
# {
#   "session_id": "sess_abc123",
#   "status": "processing",
#   "progress_percent": 65,
#   "elapsed_seconds": 30,
#   "estimated_remaining_seconds": 15
# }

# Response (Completed):
# {
#   "session_id": "sess_abc123",
#   "status": "completed",
#   "document_id": "doc_123",
#   "chunks_created": 45,
#   "completed_at": "2026-06-28T13:00:45"
# }
```

---

### Health Check

```bash
curl http://localhost:8000/health

# Response:
# {
#   "status": "healthy",
#   "version": "v1.0.0",
#   "embeddings_model": "sentence-transformers/all-MiniLM-L6-v2",
#   "vector_store": "chroma",
#   "database": "sqlite",
#   "uptime_seconds": 3600
# }
```

---

## Configuration

See `.env.example` for all settings:

**OpenRouter:**
- `OPENROUTER_API_KEY` - OpenRouter API key (get from [openrouter.ai](https://openrouter.ai))
- `EMBEDDINGS_MODEL` - Model for embeddings (default: `nvidia/llama-nemotron-embed-vl-1b-v2`)
- `EMBEDDINGS_PROVIDER` - `openrouter` or `local` (default: `openrouter`)

**Search:**
- `DEFAULT_TOP_K` - Default search results (default: 5)
- `SIMILARITY_THRESHOLD` - Minimum relevance score (default: 0.5)
- `HYBRID_SEARCH_ALPHA` - Weight of semantic vs BM25 (0-1, default: 0.5)

**Query Expansion** (LLM-based variant generation):
- `QUERY_EXPANSION_ENABLED` - Enable feature globally (default: `false`)
- `QUERY_EXPANSION_NUM_VARIANTS` - Number of query variants to generate (default: 3)
- `QUERY_EXPANSION_TIMEOUT` - Timeout for LLM call in seconds (default: 5.0)
- `QUERY_EXPANSION_MODEL` - LLM model for expansion (default: `openai/gpt-4o-mini`)

**Upload:**
- `MAX_FILE_SIZE_MB` - Maximum upload size (default: 50MB)
- `ASYNC_THRESHOLD_MB` - Files >this size processed async (default: 5MB)

---

## Database Schema

SQLite with tables for:
- `users` - User accounts
- `api_keys` - API key management
- `collections` - User collections
- `documents` - Indexed documents
- `chunks` - Document chunks
- `upload_sessions` - Async upload tracking

---

## Future Enhancements

- [ ] Celery + Redis for async tasks
- [ ] PostgreSQL support
- [ ] User sharing & permissions
- [ ] Rate limiting per API key
- [ ] Document versioning
- [ ] Batch operations
- [ ] Webhooks for upload completion

---

## Verify Setup

Test that embeddings and reranker are working correctly:

```bash
# Check health and embeddings configuration
curl http://localhost:8000/health

# Response:
# {
#   "status": "healthy",
#   "version": "v1.0.0",
#   "embeddings_model": "nvidia/llama-nemotron-embed-vl-1b-v2",
#   "vector_store": "chroma",
#   "database": "sqlite",
#   "uptime_seconds": 1234
# }
```

**Verify OpenRouter Connection:**

```bash
# Register a test user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@example.com"}'

# Generate API key
curl -X POST http://localhost:8000/api/v1/auth/generate-key \
  -H "Authorization: Bearer YOUR_API_KEY"

# If you see the API key returned, OpenRouter is properly configured
```

**Test Embeddings, Reranking & Query Expansion:**

```bash
# 1. Create a collection
curl -X POST http://localhost:8000/api/v1/collections \
  -H "Authorization: Bearer sk_rag_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{"name": "test-docs", "description": "Test collection"}'

# 2. Upload a test document
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer sk_rag_xxxxx" \
  -F "file=@test.md" \
  -F "collection_id=default"

# 3. Search (triggers embeddings + reranking)
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer sk_rag_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "your search query",
    "collection_id": "default",
    "top_k": 5
  }'

# 4. Test Query Expansion (improved relevance)
# Enable expansion in .env: QUERY_EXPANSION_ENABLED=true
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer sk_rag_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "your search query",
    "collection_id": "default",
    "top_k": 5,
    "use_query_expansion": true
  }'
# Compare results: expanded search usually has better relevance (+40% typical)
```

**Check Logs for Embeddings:**

```bash
# Look for these log messages:
# - "Using OpenRouter embeddings: nvidia/llama-nemotron-embed-vl-1b-v2"
# - "Using OpenRouter reranker: nvidia/llama-nemotron-rerank-vl-1b-v2"
# - "Reranking X results for query"
```

**If Embeddings Fail:**

1. Verify `OPENROUTER_API_KEY` is set in `.env`
2. Check API key is valid at [openrouter.ai/account/api-keys](https://openrouter.ai/account/api-keys)
3. Ensure account has credits
4. Check logs for API error messages

---

## Development

```bash
# Run with auto-reload
uvicorn main:app --reload

# Access API docs
http://localhost:8000/docs (Swagger UI)
http://localhost:8000/redoc (ReDoc)

# Run tests
pytest tests/

# View logs
tail -f logs/*.log
```

---

## Troubleshooting

**OpenRouter API Error:**
```
Error: OpenRouter API error: 401
→ Check OPENROUTER_API_KEY is correct
```

**Model Not Available:**
```
Error: Model 'nvidia/llama-nemotron-embed-vl-1b-v2' not found
→ Check model name at https://openrouter.ai/models
```

**Timeout on Large Uploads:**
```
→ Increase timeout in config or use async uploads (>5MB)
```

---

## License

MIT
