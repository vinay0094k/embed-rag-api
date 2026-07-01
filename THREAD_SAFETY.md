# Thread Safety & Concurrency

## How It Works

The API uses **thread locks** to protect the BM25 search index:

- `_bm25_lock` - Protects writes (when indexing documents)
- `_search_lock` - Protects reads (when searching)

Query expansion uses `ThreadPoolExecutor` (4 workers) for parallel searches.

---

## Limitations

**BM25 Index:** In-memory only
- Lost on process restart
- Users must re-upload documents after restart

**Bottleneck:** Single instance
- All requests share one RAGService
- Lock contention at high concurrency

---

## Performance

| Concurrent Users | Throughput | Lock Time |
|---|---|---|
| 1 | Unlimited | <1ms |
| 10 | 9500+ req/min | <5ms |
| 100 | 5000 req/min | 10-50ms |
| 500 | 800 req/min | 100-500ms |
| 1000+ | Serialized | 500ms+ |

---

## Scaling Strategy

**<100 concurrent users:**
```
User → FastAPI → SQLite + in-memory BM25 ✅
```

**100-1000 users:**
```
Users → Load Balancer → FastAPI (3-5 instances) → Redis + PostgreSQL + Elasticsearch
```

**1000+ users:**
```
Users → Load Balancer → FastAPI (10+ instances) → Elasticsearch + PostgreSQL + Redis + Celery
```

---

## Summary

✅ **Current:** Thread-safe for ~100 concurrent users  
⚠️ **Limitation:** In-memory, single-instance  
🚀 **Scale:** Need distributed search backend (Elasticsearch) for 1000+ users
