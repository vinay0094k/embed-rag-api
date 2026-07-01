#!/bin/bash

# RAG API - Clean Setup Script

echo "=========================================="
echo "RAG API - Clean Setup"
echo "=========================================="

# Remove old virtual environment if it exists
if [ -d "venv" ]; then
    echo "Removing old virtual environment..."
    rm -rf venv
fi

# Create fresh virtual environment
echo "Creating fresh virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip, setuptools, wheel
echo "Upgrading pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel

# Install requirements
echo "Installing dependencies (this may take a few minutes)..."
pip install --no-cache-dir -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Setup completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file with your OpenRouter API key:"
    echo "   nano .env"
    echo ""
    echo "2. Run the API:"
    echo "   ./run_rag_api.sh"
    echo ""
else
    echo ""
    echo "❌ Setup failed! There may be dependency conflicts."
    echo "Try running: pip install -r requirements.txt --verbose"
    exit 1
fi
