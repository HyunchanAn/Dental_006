@echo off
:: (This script starts the core services required for the Systematic Reviewer AI project for testing purposes, excluding the LLM.)

echo.
echo --- Starting Core Services for Systematic Reviewer AI (Test Mode) ---
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
echo --- Test services have been launched. ---
echo You can now run 'python main.py' to test the pipeline without the LLM.

:end
echo.
pause