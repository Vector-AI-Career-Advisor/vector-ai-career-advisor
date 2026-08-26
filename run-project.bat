@echo off
title AI Career Assistant - Full Stack Runner

echo ===============================
echo Starting Backend + Frontend...
echo ===============================

:: Go to project root
cd /d "%~dp0"

echo.
echo Project root:
echo %CD%

echo.
echo Starting Backend...
start "Backend - FastAPI" cmd /k "cd /d "%~dp0server" && "%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8000"

echo Starting Frontend...
start "Frontend - Vite" cmd /k "cd /d "%~dp0client" && npm run dev"

echo.
echo ===============================
echo Both servers are starting...
echo ===============================
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:5173
echo ===============================

pause