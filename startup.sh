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
fi

export PYTHONPATH="$(pwd):$(pwd)/college-rag-backend:$PYTHONPATH"

echo "Starting server via main:app on 0.0.0.0:8000"
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000
