# RAG API - Setup Guide

## Quick Start

```bash
cd embed-rag-api
./setup.sh
```

This will:
- Remove old venv (if exists)
- Create fresh Python venv
- Install dependencies

---

## Configure Environment

```bash
cp .env.example .env
nano .env
```

**Required:**
```
OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

Get key from: https://openrouter.ai/account/api-keys

---

## Run the API

```bash
./run_rag_api.sh
```

API available at: **http://localhost:8000/docs**

---

## Generate API Keys

```bash
python3 generate_api_key.py -u username -e email@example.com
```

Or interactive mode:
```bash
python3 generate_api_key.py
```

---

## Troubleshooting

### ModuleNotFoundError
```bash
./setup.sh
```

### Dependency conflicts
```bash
rm -rf venv
./setup.sh
```

### OPENROUTER_API_KEY not set
Add to `.env`:
```
OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

### Port 8000 already in use
```bash
lsof -ti:8000 | xargs kill -9
```

### Manual venv activation
```bash
source venv/bin/activate
uvicorn main:app --reload
```

---

## Verification

```bash
curl http://localhost:8000/health
```

Should return: `{"status": "healthy", ...}`
