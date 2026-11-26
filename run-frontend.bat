@echo off
title College RAG - Frontend (Port 5173)
cd /d "%~dp0college-rag-chat-frontend"
echo ===================================================
echo Starting React Frontend on http://localhost:5173
echo ===================================================
where npm >nul 2>nul
if %ERRORLEVEL% equ 0 (
    if not exist node_modules (
        echo Installing dependencies via npm...
        call npm install
    )
    echo Launching Vite Dev Server...
    call npm run dev
) else (
    echo Note: Node.js / npm not detected in system PATH.
    echo Serving pre-built React frontend from 'dist' on http://localhost:5173 ...
    echo [Optional] To run Vite dev server with hot reload: winget install OpenJS.NodeJS.LTS
    echo ===================================================
    "C:\Users\gdsin\AppData\Local\Programs\Python\Python313\python.exe" -m http.server 5173 --directory dist
)
pause
