$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "C:\Users\gdsin\AppData\Local\Programs\Python\Python313\python.exe"

Write-Host "Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location '$Root\college-rag-backend'; & '$Python' -m uvicorn app.main:app --reload --port 8000"

if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "Starting React/Vite frontend on http://localhost:5173 ..." -ForegroundColor Green
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location '$Root\college-rag-chat-frontend'; if (-not (Test-Path node_modules)) { npm.cmd install }; npm.cmd run dev"
} else {
    Write-Host "Built-in Chat Frontend UI is available at: http://localhost:8000" -ForegroundColor Green
    Write-Host "Backend Swagger API Docs available at:     http://localhost:8000/docs" -ForegroundColor Cyan
}

