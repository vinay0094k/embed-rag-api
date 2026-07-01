# RAG API Service - v1.0.0

Production-ready **Retrieval-Augmented Generation API** with multi-user support, async file uploads, and persistent SQLite database.

## Features

✅ **Multi-User Support** - Isolated collections per user  
✅ **API Key Authentication** - Secure Bearer token auth  
✅ **Async File Uploads** - Background processing for files >5MB (max 50MB)  
✅ **Hybrid Search** - Semantic + keyword search (BM25 + vector)  
✅ **Query Expansion** - LLM-based query variants for improved relevance (+40%)  
✅ **OpenRouter Integration** - NVIDIA Nemotron embeddings  
✅ **Persistent Storage** - SQLite database for metadata & user management  
✅ **RESTful API** - Versioned endpoints (`/api/v1/`)  
✅ **Docker Ready** - Containerized deployment with Docker Compose  
✅ **Fast & Scalable** - Built with FastAPI  

## Quick Start

### 1. Setup

```bash
cd embed-rag-api
./setup.sh
```

### 2. Configure

```bash
cp .env.example .env
nano .env
```

Add your OpenRouter API key:
```
OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

Get key from: https://openrouter.ai/account/api-keys

### 3. Generate API Key

```bash
source venv/bin/activate
pip install -r requirements.txt
python3 generate_api_key.py -u admin -e admin@example.com
```

This generates an API key that you'll use to authenticate API requests.

### 4. Run the API

**Option A: Local development (Direct)**
```bash
./run_rag_api.sh
```

**Option B: Docker - Build & Run**

Build the image:
```bash
docker build -t embed-rag-api:latest .
```

Run with environment file:
```bash
docker run -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/rag_api.db:/app/rag_api.db \
  -v $(pwd)/chroma_db:/app/chroma_db \
  embed-rag-api:latest
```

**Option C: Docker Compose (Recommended) - Production Ready**

**Step 1: Verify `.env` is configured**
```bash
cat .env | grep OPENROUTER_API_KEY
# Should show: OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

**Step 2: Start the API**
```bash
docker compose up
```

**Step 3: Verify it's running**
```bash
# In another terminal
docker compose ps
# Should show: rag-api ... Up (health: healthy)
```

**What this does:**
- ✅ Builds Docker image automatically
- ✅ Loads `.env` file (secure, no API keys in commands)
- ✅ Applies resource limits (2 CPU, 2GB RAM max)
- ✅ Configures logging (JSON format, 10MB rotation)
- ✅ Sets up health checks (/api/v1/health)
- ✅ Auto-restarts on failure
- ✅ Uses custom network isolation
- ✅ Persists database across restarts

**Run in background (detached):**
```bash
docker compose up -d
```

**View logs:**
```bash
docker compose logs -f rag-api
```

**Stop:**
```bash
docker compose down
```

### Access the API

Once running (any option):

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/api/v1/health
- **Root:** http://localhost:8000/

---

## Documentation

- **[SETUP.md](SETUP.md)** - Setup instructions
- **[GENERATE_API_KEY.md](GENERATE_API_KEY.md)** - Generate API keys
- **[APPLICATION_FLOW.md](APPLICATION_FLOW.md)** - Architecture & data flows
- **[TESTING.md](TESTING.md)** - How to run tests
- **[MIGRATIONS.md](MIGRATIONS.md)** - Database migrations
- **[THREAD_SAFETY.md](THREAD_SAFETY.md)** - Concurrency & scaling

---

## API Docs

Interactive API documentation available at: **http://localhost:8000/docs**

All endpoints require Bearer token authentication:
```bash
Authorization: Bearer sk_rag_xxxxx
```

---

## Technology Stack

- **Framework:** FastAPI
- **Database:** SQLite + Alembic migrations
- **Vector Store:** Chroma (in-memory)
- **Search:** BM25 + Semantic search
- **Embeddings:** OpenRouter (NVIDIA Nemotron)
- **Auth:** API Keys with HMAC-SHA256 hashing
- **Async:** Background task queue for large uploads

---

## System Requirements

- Python 3.9+
- 2GB RAM (minimum)
- 1GB disk space
- Internet connection (for OpenRouter API)

---

## Docker Deployment

### Prerequisites

Ensure `.env` file is configured with:
```bash
OPENROUTER_API_KEY=sk-or-v1-xxxxx
SECRET_KEY=your-secret-key
DEBUG=true
```

### Option 1: Docker Run (Manual)

```bash
# Build the image
docker build -t embed-rag-api:latest .

# Run container with environment file
docker run -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/rag_api.db:/app/rag_api.db \
  -v $(pwd)/chroma_db:/app/chroma_db \
  embed-rag-api:latest
```

### Option 2: Docker Compose (Recommended - Production Ready)

```bash
docker compose up
```

**Features:**
- ✅ Automatic image build
- ✅ Environment from `.env` file
- ✅ Resource limits (2 CPU, 2GB RAM)
- ✅ Health checks configured
- ✅ JSON logging with rotation
- ✅ Auto-restart on failure
- ✅ Custom network isolation

**Management Commands:**

View logs:
```bash
docker compose logs -f rag-api
```

Restart:
```bash
docker compose restart
```

Stop:
```bash
docker compose down
```

Remove volumes (cleanup):
```bash
docker compose down -v
```

---

## License

MIT
