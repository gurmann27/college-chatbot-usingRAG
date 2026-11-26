@echo off
echo Launching Backend and Frontend in separate terminals...
start "College RAG - Backend" cmd.exe /c "%~dp0run-backend.bat"
start "College RAG - Frontend" cmd.exe /c "%~dp0run-frontend.bat"
echo Done! Both terminals have been launched.
