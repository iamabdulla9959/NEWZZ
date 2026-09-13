@echo off
:: Launches the news crawler in a visible terminal window with one click
cd /d "%~dp0"
echo Starting Automated News Crawler (10-minute cycle)...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" auto_news_crawler.py
) else if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" auto_news_crawler.py
) else (
    python auto_news_crawler.py
)
pause
