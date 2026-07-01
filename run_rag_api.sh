#!/bin/bash

# RAG API - Setup and Run Script

echo "=========================================="
echo "RAG API - Setup and Run"
echo "=========================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install requirements
echo "Installing dependencies..."
pip install --upgrade pip setuptools wheel
pip install --no-cache-dir -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your OPENROUTER_API_KEY"
    echo "Edit: .env"
    echo "Then run this script again"
    exit 1
fi

# Check if OPENROUTER_API_KEY is set
if ! grep -q "OPENROUTER_API_KEY=sk-or" .env; then
    echo "❌ OPENROUTER_API_KEY not configured in .env"
    echo "Please edit .env and add your OpenRouter API key"
    echo "Get one from: https://openrouter.ai/account/api-keys"
    exit 1
fi

# Create directories if they don't exist
mkdir -p chroma_db knowledge_base temp_uploads logs

# Kill any existing process on port 8000
if lsof -ti:8000 &>/dev/null; then
    echo "Killing existing process on port 8000..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    sleep 1
fi

echo ""
echo "=========================================="
echo "Starting RAG API..."
echo "=========================================="
echo "API will be available at: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Health Check: http://localhost:8000/health"
echo ""
echo "To generate API key (only needed once):"
echo "  python3 generate_api_key.py -u username -e email@example.com"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="

# Run the RAG API with reload exclusions (avoid infinite restart loop)
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug

