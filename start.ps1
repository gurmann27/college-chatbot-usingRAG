$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Launching Backend and Frontend in separate terminals..." -ForegroundColor Cyan
Start-Process cmd.exe -ArgumentList "/c", "`"$Root\run-backend.bat`""
Start-Process cmd.exe -ArgumentList "/c", "`"$Root\run-frontend.bat`""

Write-Host "Done! Launched separate terminals for:" -ForegroundColor Green
Write-Host "  - Backend (FastAPI):  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  - Frontend (React):   http://localhost:5173" -ForegroundColor Cyan
