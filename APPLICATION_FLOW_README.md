# Embed-RAG-API: Complete Flow

## **High-Level Architecture**

```
┌─────────────┐
│   Client    │ (curl, Python, frontend)
└──────┬──────┘
       │ HTTP Request
       ▼
┌──────────────────────────────────────────────┐
│         FastAPI Application (main.py)         │
├──────────────────────────────────────────────┤
│ ┌────────────────────────────────────────┐   │
│ │  Middleware Stack (bottom → top)       │   │
│ ├────────────────────────────────────────┤   │
│ │ 1. RequestTracingMiddleware            │   │ ← Request ID + logging
│ │ 2. RateLimitMiddleware                 │   │ ← 10-100 req/min limits
│ │ 3. CORSMiddleware                      │   │ ← CORS headers
│ └────────────────────────────────────────┘   │
│                    ↓                          │
│ ┌────────────────────────────────────────┐   │
│ │  Exception Handlers (Global)           │   │ ← Catch all errors
│ └────────────────────────────────────────┘   │
│                    ↓                          │
│ ┌────────────────────────────────────────┐   │
│ │  Route Handlers (v1 endpoints)         │   │
│ │  /auth, /collections, /documents,      │   │
│ │  /search, /uploads, /health            │   │
│ └────────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
       │ JSON Response
       ▼
┌─────────────┐
│   Client    │ (with X-Request-ID header)
└─────────────┘
```

---

## **1. REQUEST AUTHENTICATION FLOW**

```
Client Request with API Key
    ↓
Middleware: Add X-Request-ID, rate limit check
    ↓
Route Handler
    ↓
Dependency: get_current_user()
    ├─ Extract "Bearer <key>" from Authorization header
    ├─ Hash the key: HMAC-SHA256(key + SECRET_KEY)
    ├─ Query DB: APIKey.filter(key_hash == hash)
    ├─ Verify user is active
    └─ Return User object
    ↓
Route proceeds with authenticated User
    ↓
Response with X-Request-ID header
```

**Key Files:**
- `app/core/security.py` - `get_current_user()`
- `app/core/crypto.py` - `hash_api_key()`
- `app/db/crud.py` - `APIKeyCRUD.get_api_key()`

---

## **2. DOCUMENT UPLOAD FLOW**

### **Small File (<5MB) - Synchronous**

```
POST /api/v1/documents/upload
    ↓
1. Validate file (extension, size)
    ├─ Check: only .txt or .md
    └─ Check: <50MB
    ↓
2. Verify collection exists (user isolation)
    ├─ Only user's own collections accessible
    └─ 403 if not owner
    ↓
3. Check file size → is_async_upload()
    └─ If <5MB: proceed synchronously
    ↓
4. Save file to disk
    └─ /temp_uploads/<uuid>
    ↓
5. Load document
    └─ DocumentLoader.load(file_path)
    ├─ Extracts text from .md or .txt
    └─ Returns List[Document]
    ↓
6. Chunk document
    └─ StructureAwareChunker.chunk(docs)
    ├─ Splits into ~500 token chunks
    ├─ Preserves structure (code blocks, headers, etc.)
    └─ Returns List[DocumentChunk]
    ↓
7. Embed chunks (async call)
    └─ OpenRouterEmbeddings.embed(texts)
    ├─ Calls: https://openrouter.ai/api/v1/embeddings
    ├─ Model: nvidia/llama-nemotron-embed-vl-1b-v2
    └─ Returns List[List[float]] (vectors)
    ↓
8. Index chunks (thread-safe)
    ├─ WITH _bm25_lock:
    │  ├─ Add to BM25Index (keyword search)
    │  └─ Add to HybridVectorStore (vector DB)
    └─ Chroma stores vectors + metadata
    ↓
9. Update document status → INDEXED
    └─ Store in SQLite: Document.status = "INDEXED"
    ↓
200 OK: DocumentUploadResponse
    ├─ status: "success"
    ├─ document_id
    └─ chunks_created
```

### **Large File (>5MB) - Asynchronous**

```
POST /api/v1/documents/upload (>5MB)
    ↓
1-3. [Same as sync: validate, verify collection, check size]
    ↓
4. Create UploadSession record
    └─ status = "UPLOADING"
    ├─ filename, file_size, progress_percent=0
    └─ Store in DB
    ↓
5. Save file to disk
    └─ /temp_uploads/<uuid>
    ↓
6. QUEUE BACKGROUND TASK (return immediately)
    ├─ enqueue_task(
    │  ├─ task_id = session.id
    │  ├─ func = process_document_background()
    │  └─ args = (file_path, collection_id, user_id, ...)
    │ )
    ├─ Add to BackgroundTaskQueue
    └─ Worker thread will pick it up
    ↓
200 OK: AsyncUploadResponse
    ├─ status: "processing"
    ├─ session_id
    ├─ status_url: "/api/v1/uploads/{session_id}/status"
    └─ estimated_time_seconds: 60
    ↓
[Client polls for progress]
    ├─ GET /api/v1/uploads/{session_id}/status
    ├─ Returns: progress_percent, status, elapsed_seconds
    └─ Repeat until status = "completed"
    ↓
[Background worker processes]
    ├─ Thread from BackgroundTaskQueue picks up task
    ├─ Steps 5-9 from sync flow (load, chunk, embed, index)
    ├─ Update UploadSession.progress_percent
    ├─ On completion: status = "completed"
    └─ Cleanup temp file
```

**Key Files:**
- `app/api/v1/endpoints/documents.py` - Upload endpoint
- `app/services/document_service.py` - Validation, async check
- `app/tasks/background.py` - Task queue, worker threads
- `app/services/rag_service.py` - Load, chunk, index

---

## **3. SEARCH / RAG FLOW (WITH QUERY EXPANSION)**

```
POST /api/v1/search
{
  "query": "how to deploy kubernetes?",
  "collection_id": "default",
  "top_k": 5,
  "use_query_expansion": true,
  "use_rerank": true
}
    ↓
1. Validate request
    └─ Verify collection belongs to user
    ↓
2. Query Expansion (if enabled)
    ├─ QueryExpansionService.generate_variants(query, num_variants=3, timeout=5s)
    │  ├─ Call: https://openrouter.ai/api/v1/chat/completions
    │  ├─ Model: openai/gpt-4o-mini
    │  ├─ Prompt: "Generate 3 different search queries capturing different aspects"
    │  ├─ Variants generated:
    │  │  ├─ "kubernetes deployment guide"
    │  │  ├─ "kubectl apply deployment steps"
    │  │  └─ "kubernetes pod deployment best practices"
    │  │
    │  ├─ On timeout/error: return empty list (graceful degradation)
    │  └─ Proceed with: [original_query, variant1, variant2, variant3]
    │
    ├─ NOTE: If no expansion, queries_to_search = [original_query]
    └─ Timeout: 5 seconds (QUERY_EXPANSION_TIMEOUT config)
    ↓
3. Parallel Hybrid Search (if expansion used)
    ├─ ThreadPoolExecutor (max 4 workers)
    ├─ For each query in queries_to_search:
    │  ├─ Vector search (semantic)
    │  │  └─ OpenRouterEmbeddings.embed(query)
    │  │     ├─ Call: https://openrouter.ai/api/v1/embeddings
    │  │     └─ Get query vector
    │  │
    │  ├─ HybridVectorStore.hybrid_search()
    │  │  ├─ Semantic: Chroma cosine similarity
    │  │  ├─ Keyword: BM25 TF-IDF matching
    │  │  ├─ Combine: alpha*semantic + (1-alpha)*keyword
    │  │  └─ Return top_k*2 results
    │  │
    │  └─ Thread-safe: WITH _bm25_lock (read lock)
    │
    ├─ Merge Results (deduplication by chunk_id)
    │  ├─ For each chunk_id: keep max score
    │  ├─ Sort by score descending
    │  └─ Return top_k
    │
    └─ If no expansion: single query search (standard flow)
    ↓
4. Rerank results (if enabled)
    ├─ Take top_k results
    ├─ OpenRouterReranker.rerank(query, docs)
    │  ├─ Call: https://openrouter.ai/api/v1/embeddings
    │  ├─ Model: nvidia/llama-nemotron-rerank-vl-1b-v2
    │  ├─ Score documents by relevance
    │  └─ Return ranked list
    └─ Sort by relevance score
    ↓
5. Return top_k results
    └─ SearchResponse
        ├─ query: "how to deploy kubernetes?"
        ├─ results: [SearchResultItem, ...]
        │  ├─ content: "chunk text..."
        │  ├─ source: "document_id"
        │  ├─ score: 0.92 (improved by expansion)
        │  └─ metadata: {...}
        ├─ search_time_ms: 2150.4 (includes expansion + parallel searches)
        └─ result_count: 5
```

**Query Expansion Features:**
- ✅ Optional per-request via `use_query_expansion` parameter
- ✅ Configurable globally via `QUERY_EXPANSION_ENABLED` env var
- ✅ Graceful degradation: timeout/error → uses original query only
- ✅ Parallel execution: all query variants searched in parallel
- ✅ Result merging: deduplicates by chunk_id, keeps max score

**Configuration:**
```
QUERY_EXPANSION_ENABLED=true/false     # Enable feature
QUERY_EXPANSION_NUM_VARIANTS=3         # Number of variants to generate
QUERY_EXPANSION_TIMEOUT=5.0            # Timeout in seconds
QUERY_EXPANSION_MODEL=openai/gpt-4o-mini  # LLM model for variants
OPENROUTER_API_KEY=sk-xxx             # Required for expansion
```

**Key Files:**
- `app/api/v1/endpoints/search.py` - Search endpoint
- `app/services/rag_service.py` - `search()` method with expansion logic
- `app/services/expansion_service.py` - Query variant generation
- `app/services/embedding_service.py` - Async embeddings
- `app/services/reranker_service.py` - Reranking
- `app/rag_components/vector_store.py` - Hybrid search

---

## **4. DATABASE LAYER FLOW**

```
Request comes in
    ↓
get_db() dependency
    ├─ SessionLocal() creates session
    ├─ Yields to route handler
    └─ Closes after response
    ↓
CRUD operations in route
    ├─ UserCRUD.get_user_by_id(db, user_id)
    ├─ CollectionCRUD.create_collection(db, ...)
    ├─ DocumentCRUD.create_document(db, ...)
    ├─ APIKeyCRUD.get_api_key(db, key_hash)
    └─ UploadSessionCRUD.* (for async tracking)
    ↓
SQLite Database
    ├─ users
    ├─ api_keys (with key_hash column)
    ├─ collections
    ├─ documents
    ├─ chunks
    └─ upload_sessions
    ↓
Response returned
```

**Key Files:**
- `app/db/database.py` - Engine, SessionLocal, init_db()
- `app/db/models.py` - SQLAlchemy ORM models
- `app/db/crud.py` - CRUD operations
- `alembic/versions/506e088bc6de_initial_schema.py` - Schema migration

---

## **5. LOGGING & TRACING FLOW**

```
Request arrives
    ↓
RequestTracingMiddleware
    ├─ Extract or generate X-Request-ID
    ├─ Store in context variable
    ├─ Log: "→ GET /api/v1/collections"
    └─ Add to request.state
    ↓
Route handler executes
    ├─ All logs automatically include request_id
    │  Example: {"message": "...", "request_id": "uuid", ...}
    └─ Structured JSON format
    ↓
Exception handler (if error)
    ├─ Catch exception
    ├─ Log with request_id
    ├─ Format as ErrorResponse JSON
    └─ Return with request_id in response body
    ↓
Response sent
    ├─ Add X-Request-ID header
    ├─ Log: "← GET /api/v1/collections 200 (45ms)"
    └─ Trace complete
```

**Key Files:**
- `app/core/logging.py` - StructuredFormatter, context vars
- `app/core/middleware.py` - RequestTracingMiddleware
- `app/core/exception_handlers.py` - Global error handler

---

## **6. RATE LIMITING FLOW**

```
Request arrives
    ↓
RateLimitMiddleware
    ├─ Get identifier
    │  ├─ If Bearer token: use API key
    │  └─ Else: use client IP
    │
    ├─ Select limiter
    │  ├─ /auth/* → 10 req/min (strict)
    │  ├─ /api/* with token → 100 req/min (standard)
    │  └─ Anonymous → 20 req/min (generous)
    │
    ├─ Token bucket algorithm
    │  ├─ Check tokens available
    │  ├─ If yes: decrement and proceed
    │  └─ If no: return 429 Too Many Requests
    │
    └─ Periodically cleanup old buckets (prevent memory leak)
```

**Key Files:**
- `app/core/rate_limiter.py` - RateLimiter class, middleware

---

## **7. COMPLETE REQUEST LIFECYCLE EXAMPLE (WITH QUERY EXPANSION)**

```
User: curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer sk_rag_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{"query": "deploy kubernetes", "use_query_expansion": true, "top_k": 5}'
    │
    ├─→ uvicorn receives request
    │
    ├─→ RequestTracingMiddleware
    │    └─ Generate request_id: "550e8400-e29b-41d4..."
    │       Log: "→ POST /api/v1/search"
    │
    ├─→ RateLimitMiddleware
    │    └─ API key: sk_rag_xxxxx → limit: 100 req/min
    │       Status: OK (proceed)
    │
    ├─→ CORSMiddleware
    │    └─ Check origin, add CORS headers
    │
    ├─→ Route: POST /api/v1/search
    │
    ├─→ Dependency: get_current_user()
    │    ├─ Extract key: "sk_rag_xxxxx"
    │    ├─ Hash: HMAC-SHA256(key + SECRET_KEY)
    │    ├─ Query DB: APIKey.filter(key_hash == hash)
    │    ├─ User: valid, active ✓
    │    └─ Proceed with User object
    │
    ├─→ Dependency: get_db()
    │    └─ Create SessionLocal() session
    │
    ├─→ Handler: search()
    │    ├─ Verify collection belongs to user
    │    │
    │    ├─ Query Expansion (if use_query_expansion=true)
    │    │  ├─ QueryExpansionService.generate_variants()
    │    │  │  ├─ Call OpenRouter chat API (timeout: 5s)
    │    │  │  ├─ Model: openai/gpt-4o-mini
    │    │  │  └─ Returns: ["deploy kubernetes", "kubectl deployment guide", "k8s pod setup"]
    │    │  │
    │    │  └─ queries_to_search = [original + 3 variants]
    │    │
    │    ├─ Parallel Hybrid Search (ThreadPoolExecutor, 4 workers)
    │    │  ├─ Query 1: "deploy kubernetes"
    │    │  │  ├─ Embed via OpenRouter
    │    │  │  ├─ WITH _bm25_lock: Hybrid search
    │    │  │  └─ Return top 10 results
    │    │  │
    │    │  ├─ Query 2: "kubectl deployment guide"
    │    │  │  ├─ Embed via OpenRouter
    │    │  │  ├─ WITH _bm25_lock: Hybrid search
    │    │  │  └─ Return top 10 results
    │    │  │
    │    │  ├─ Query 3: "k8s pod setup"
    │    │  │  ├─ (parallel execution)
    │    │  │  └─ Return top 10 results
    │    │  │
    │    │  └─ Merge all results (dedup by chunk_id, keep max score)
    │    │
    │    ├─ Rerank results (if enabled)
    │    │  ├─ Call OpenRouter reranker
    │    │  └─ Score by relevance
    │    │
    │    └─ Return top 5 SearchResponse (improved by expansion)
    │
    ├─→ Exception handler (if error)
    │    ├─ Expansion timeout: proceed with original query (graceful)
    │    └─ Format error, include request_id
    │
    ├─→ Response object
    │    ├─ Add X-Request-ID header
    │    ├─ JSON content:
    │    │  {
    │    │    "query": "deploy kubernetes",
    │    │    "results": [
    │    │      {"content": "...", "score": 0.95, ...},
    │    │      ...
    │    │    ],
    │    │    "search_time_ms": 2150.4,
    │    │    "result_count": 5
    │    │  }
    │    └─ status_code: 200
    │
    ├─→ RequestTracingMiddleware (after handler)
    │    └─ Log: "← POST /api/v1/search 200 (2150ms)"
    │
    └─→ uvicorn sends response
         Client receives: {"query": "...", "results": [...], "X-Request-ID": "550e8400..."}
```

---

## **8. THREAD SAFETY & CONCURRENCY**

```
Concurrent Requests (10 users searching simultaneously)
    │
    ├─→ Request 1: Search query
    │    └─ Acquires _search_lock
    │       ├─ Performs hybrid_search
    │       ├─ Releases lock
    │       └─ Reranks (no lock)
    │
    ├─→ Request 2: Upload document (>5MB)
    │    └─ Queues background task
    │       Background worker acquires _bm25_lock
    │       ├─ Loads document
    │       ├─ Chunks
    │       ├─ Embeds
    │       ├─ Acquires _bm25_lock
    │       ├─ Indexes chunks
    │       └─ Releases _bm25_lock
    │
    ├─→ Request 3: Search query
    │    └─ Waits for Request 1's lock
    │       Once available, acquires and searches
    │
    └─→ All requests proceed safely
        No corruption of BM25 or vector store
```

**Locks:**
- `RAGService._bm25_lock` - Protects writes to BM25Index
- `RAGService._search_lock` - Protects reads during hybrid_search
- `_rag_service_lock` - Double-checked locking for singleton creation

---

## **9. BACKGROUND TASK PROCESSING**

```
Async Upload (>5MB)
    │
    ├─→ Request queues task
    │    └─ Task added to BackgroundTaskQueue
    │
    ├─→ Returns 202 ACCEPTED immediately
    │    └─ Client gets session_id for polling
    │
    ├─→ Background Worker Thread 1
    │    ├─ Picks up task from queue
    │    ├─ Executes: process_document_background()
    │    ├─ Steps:
    │    │  ├─ Load document
    │    │  ├─ Chunk document
    │    │  ├─ Embed chunks
    │    │  ├─ Index chunks (with _bm25_lock)
    │    │  ├─ Update DB: status = "completed"
    │    │  └─ Cleanup temp file
    │    └─ Logs progress
    │
    ├─→ Client polls meanwhile
    │    ├─ GET /api/v1/uploads/{session_id}/status
    │    ├─ Returns: progress_percent, status
    │    └─ Repeat until status = "completed"
    │
    └─→ Task complete
         Client sees document indexed and ready to search
```

**Key Files:**
- `app/tasks/background.py` - BackgroundTaskQueue, worker threads
- `app/api/v1/endpoints/documents.py` - Async upload logic
- `app/api/v1/endpoints/uploads.py` - Status polling endpoint

---

## **Summary: Data Flow End-to-End**

```
User Input
    ↓
API Request + Authentication
    ↓
Rate Limiting & Request Tracing
    ↓
Route Handler + CRUD Operations
    ↓
RAG Service (embeddings, search, reranking)
    ├─ Optional Query Expansion (LLM-based variants)
    │  ├─ Parallel multi-query search
    │  └─ Result deduplication & merging
    ├─ Async HTTP to OpenRouter
    ├─ Thread-safe access to BM25 + vector store
    └─ Background task processing
    ↓
Database Persistence (SQLite + Alembic)
    ↓
Structured JSON Response + Request ID
    ↓
Middleware logging (all request_id)
    ↓
Client receives response
```

All with:
✅ Security (auth, hashing, rate limiting)
✅ Reliability (locks, error handling, graceful shutdown, timeout handling)
✅ Observability (request tracing, structured logging)
✅ Performance (async, background tasks, caching, parallel searches)
✅ Quality (query expansion for improved relevance, reranking)
