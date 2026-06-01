@echo off
:: (This script starts the core services required for the Systematic Reviewer AI project.)

:: Change directory to the script's location to ensure relative paths work correctly
cd /d "%~dp0"

echo.
echo --- Starting Core Services for Systematic Reviewer AI ---
echo.

:: --- 1. GROBID 서비스 시작 (Docker) ---
echo [1/1] Starting GROBID service using Docker...
echo      (This will run in the background)
cd tools\grobid
docker-compose up -d
cd ..\..
echo GROBID service started.
echo.

echo.
echo --- All necessary services have been launched. ---
echo The Ollama LLM server runs automatically in the background.
echo You can now run 'python main.py' in this terminal.
echo.
pause