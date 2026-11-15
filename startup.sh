#!/bin/bash
set -e

echo "=== Starting College RAG Chatbot on Azure App Service ==="

# 1. Activate Azure virtual environment if present
if [ -d "/antenv" ]; then
    echo "Activating /antenv"
    source /antenv/bin/activate
elif [ -n "$VIRTUAL_ENVIRONMENT" ]; then
    echo "Activating $VIRTUAL_ENVIRONMENT"
    source "$VIRTUAL_ENVIRONMENT/bin/activate"
elif [ -d "antenv" ]; then
    echo "Activating ./antenv"
    source antenv/bin/activate
fi

# 2. Ensure uvicorn is available, install if missing
if ! command -v uvicorn &> /dev/null; then
    echo "uvicorn not found in PATH, installing requirements..."
    pip install --no-cache-dir -r requirements.txt
fi

# 3. Determine port: Azure provides $PORT, fallback to 8000
APP_PORT="${PORT:-8000}"
echo "Binding server to 0.0.0.0:${APP_PORT}"

# 4. Start backend
cd college-rag-backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT}"
