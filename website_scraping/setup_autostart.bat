@echo off
:: Configures the news crawler to start automatically on Windows login
set "SCRIPT_DIR=%~dp0"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET_FILE=%STARTUP_DIR%\NewsCrawlerAutoStart.vbs"

echo Setting up automatic startup on Windows login...
copy /y "%SCRIPT_DIR%run_background.vbs" "%TARGET_FILE%" >nul
if %errorlevel% equ 0 (
    echo.
    echo ======================================================================
    echo [SUCCESS] Automated startup is now active!
    echo Whenever your computer starts or you log in, the news crawler will
    echo run automatically in the background without opening any terminal.
    echo ======================================================================
) else (
    echo [ERROR] Failed to copy to Startup folder.
)
echo.
pause
