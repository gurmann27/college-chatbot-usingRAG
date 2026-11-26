@echo off
title College RAG - Backend (Port 8000)
cd /d "%~dp0college-rag-backend"
echo ===================================================
echo Starting FastAPI Backend on http://localhost:8000
echo Swagger API Docs: http://localhost:8000/docs
echo ===================================================
"C:\Users\gdsin\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn app.main:app --reload --port 8000
pause
