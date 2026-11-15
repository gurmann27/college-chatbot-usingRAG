#!/bin/bash
set -e

echo "=== Starting College RAG Chatbot on Azure App Service ==="

# 1. Add python packages to PYTHONPATH and PATH
if [ -d "/home/site/wwwroot/.python_packages/lib/site-packages" ]; then
    export PYTHONPATH="/home/site/wwwroot/.python_packages/lib/site-packages:$PYTHONPATH"
    export PATH="/home/site/wwwroot/.python_packages/bin:$PATH"
fi
if [ -d ".python_packages/lib/site-packages" ]; then
    export PYTHONPATH="$(pwd)/.python_packages/lib/site-packages:$PYTHONPATH"
    export PATH="$(pwd)/.python_packages/bin:$PATH"
fi

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

# 2. Add backend folder to PYTHONPATH
export PYTHONPATH="$(pwd)/college-rag-backend:$PYTHONPATH"

# 3. Ensure uvicorn and fastapi are available, install if missing
if ! python -c "import uvicorn, fastapi" &> /dev/null; then
    echo "uvicorn or fastapi not found, installing requirements..."
    python -m pip install --no-cache-dir -r requirements.txt
fi

# 4. Determine port: Azure provides $PORT, fallback to $WEBSITES_PORT, then 8000
APP_PORT="${PORT:-${WEBSITES_PORT:-8000}}"
echo "Binding server to 0.0.0.0:${APP_PORT}"

# 5. Start backend
cd college-rag-backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT}"
