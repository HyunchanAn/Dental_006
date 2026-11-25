@echo off
:: (This script starts the core services required for the Systematic Reviewer AI project for testing purposes, excluding the LLM.)

cd /d "%~dp0\.."

echo.
echo --- Starting Core Services for Systematic Reviewer AI (Test Mode) ---
echo.

:: --- 1. GROBID service via root docker-compose.yml ---
echo [1/1] Starting GROBID service using Docker...
echo      (This will run in the background)
docker compose up -d grobid
echo GROBID service started.
echo.

echo.
echo --- Test services have been launched. ---
echo You can now run 'python main.py' to test the pipeline without the LLM.

:end
echo.
pause
