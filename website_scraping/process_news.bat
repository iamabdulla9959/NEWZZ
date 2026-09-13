@echo off
:: Runs the news processing engine (deduplicate, summarize, rank important-wise)
cd /d "%~dp0"
echo =========================================================================
echo News Processing Engine (Deduplicate, Summarize, Rank Importance)
echo =========================================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" process_news.py %*
) else if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" process_news.py %*
) else (
    python process_news.py %*
)
pause
