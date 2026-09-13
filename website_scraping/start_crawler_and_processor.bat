@echo off
:: Launches the News Crawler Bot and Processing Engine together in sync
cd /d "%~dp0"
echo =========================================================================
echo Launching Automated News Crawler + Deduplication/Summarizer Pipeline
echo =========================================================================
echo.
echo 1. The Crawler searches feeds every 10 min and updates news.json
echo 2. The Processor takes news, deduplicates, summarizes, and ranks by importance
echo.

set PY_CMD=python
if exist ".venv\Scripts\python.exe" set PY_CMD=".venv\Scripts\python.exe"
if exist "..\.venv\Scripts\python.exe" set PY_CMD="..\.venv\Scripts\python.exe"

start "News Crawler Bot (Every 10 min)" %PY_CMD% auto_news_crawler.py
timeout /t 3 >nul
%PY_CMD% process_news.py --watch
pause
