# RAG API - Complete Setup Guide

## **Quick Start**

### **Step 1: Clean Setup (Recommended for first-time or conflicts)**

```bash
cd /home/vinayk/Documents/Daily_Documents/embed-rag-api
./setup.sh
```

This will:
- ✓ Remove old virtual environment
- ✓ Create fresh Python 3.12 venv
- ✓ Upgrade pip, setuptools, wheel
- ✓ Install all dependencies
- ✓ Show next steps

### **Step 2: Configure OpenRouter API Key**

```bash
# Edit .env file
nano .env
```

Add your OpenRouter API key:
```
OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY_HERE
EMBEDDINGS_PROVIDER=openrouter
EMBEDDINGS_MODEL=nvidia/llama-nemotron-embed-vl-1b-v2
```

Get API key: https://openrouter.ai/account/api-keys

### **Step 3: Run the API**

```bash
./run.sh
```

Your API will be available at: **http://localhost:8000**

---

## **Detailed Setup Instructions**

### **1. Clean Installation**

For a complete fresh setup (recommended):

```bash
cd /home/vinayk/Documents/Daily_Documents/embed-rag-api

# Run clean setup
./setup.sh

# Output:
# Creating fresh virtual environment...
# Activating virtual environment...
# Upgrading pip, setuptools, wheel...
# Installing dependencies...
# ✓ Setup completed successfully!
```

### **2. Configure Environment Variables**

```bash
# Copy example to .env
cp .env.example .env

# Edit with your settings
nano .env
```

**Required:**
```
OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

**Optional (defaults shown):**
```
EMBEDDINGS_PROVIDER=openrouter
EMBEDDINGS_MODEL=nvidia/llama-nemotron-embed-vl-1b-v2
DATABASE_URL=sqlite:///./rag_api.db
MAX_FILE_SIZE_MB=50
ASYNC_THRESHOLD_MB=5
DEFAULT_TOP_K=5
SIMILARITY_THRESHOLD=0.5

# Query Expansion (LLM-based query variants for +40% relevance)
QUERY_EXPANSION_ENABLED=false
QUERY_EXPANSION_NUM_VARIANTS=3
QUERY_EXPANSION_TIMEOUT=5.0
QUERY_EXPANSION_MODEL=openai/gpt-4o-mini
```

### **3. Start the API**

```bash
./run.sh
```

This will:
1. Activate virtual environment
2. Install dependencies
3. Validate configuration
4. Auto-generate admin API key
5. Start the API server

**Output:**
```
==========================================
RAG API - Setup and Run
==========================================
Installing dependencies...

==========================================
Generating API Key...
==========================================
API Key: sk_rag_Km75KU833hMXXYHFcfTbYFqeWWeisGleolCZy6Y99xw

==========================================
Starting RAG API...
==========================================
API will be available at: http://localhost:8000
API Docs: http://localhost:8000/docs
Press Ctrl+C to stop the server
```

---

## **Verification**

### **Check API Health**

```bash
curl http://localhost:8000/health

# Should return:
# {
#   "status": "healthy",
#   "version": "v1.0.0",
#   "embeddings_model": "nvidia/llama-nemotron-embed-vl-1b-v2",
#   ...
# }
```

### **Access API Documentation**

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### **Generate Additional API Keys**

```bash
python3 generate_api_key.py -u username -e email@example.com
```

---

## **Troubleshooting**

### **Issue: ModuleNotFoundError**

```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:** Run clean setup
```bash
./setup.sh
```

### **Issue: ResolutionImpossible dependency conflict**

```
ERROR: ResolutionImpossible: for help visit...
```

**Solution:** Clean installation with flexible dependencies
```bash
rm -rf venv
./setup.sh
```

### **Issue: OPENROUTER_API_KEY not set**

```
❌ OPENROUTER_API_KEY not configured in .env
```

**Solution:**
1. Edit `.env` file
2. Add your OpenRouter API key: `OPENROUTER_API_KEY=sk-or-v1-xxxxx`
3. Save and run `./run.sh` again

### **Issue: Port 8000 already in use**

```
Address already in use
```

**Solution:** Change port in `.env` or stop the other service
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### **Issue: Virtual environment not activating**

Try manual activation:
```bash
source venv/bin/activate

# Then run API
uvicorn main:app --reload
```

---

## **Development Setup**

For active development:

```bash
# 1. Setup
./setup.sh

# 2. Configure
nano .env

# 3. Run with auto-reload
./run.sh

# 4. In another terminal, generate API key
python3 generate_api_key.py -u dev -e dev@example.com

# 5. Test endpoints
curl -H "Authorization: Bearer sk_rag_xxxxx" http://localhost:8000/api/v1/health
```

---

## **Production Setup**

For production deployment with Docker:

```bash
# Build image
docker build -t rag-api:latest .

# Run container
docker run -p 8000:8000 \
  -e OPENROUTER_API_KEY=sk-or-v1-xxxxx \
  -e DATABASE_URL=sqlite:///./rag_api.db \
  rag-api:latest

# Or with Docker Compose
docker-compose up
```

---

## **System Requirements**

- Python 3.9+
- 2GB RAM (minimum)
- 1GB disk space
- Internet connection (for OpenRouter API)

---

## **Next Steps**

1. ✓ Run `./setup.sh`
2. ✓ Configure `.env` with OpenRouter API key
3. ✓ Run `./run.sh`
4. ✓ Visit http://localhost:8000/docs
5. ✓ Generate API keys with `python3 generate_api_key.py`
6. ✓ Start using the API!

---

## **Support**

For issues:
1. Check logs: `tail -f logs/rag_api.log`
2. Verify OpenRouter API key at: https://openrouter.ai/account/api-keys
3. Test health endpoint: `curl http://localhost:8000/health`
4. Check .env file: `cat .env`
