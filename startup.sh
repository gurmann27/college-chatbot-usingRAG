#!/bin/bash
set -e
export PYTHONPATH="/home/site/wwwroot/.python_packages/lib/site-packages:/home/site/wwwroot/college-rag-backend:$PYTHONPATH"
cd /home/site/wwwroot 2>/dev/null || true
python main.py
