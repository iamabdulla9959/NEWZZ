@echo off
:: Removes automatic startup from Windows login
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET_FILE=%STARTUP_DIR%\NewsCrawlerAutoStart.vbs"

if exist "%TARGET_FILE%" (
    del /f /q "%TARGET_FILE%"
    echo.
    echo [SUCCESS] Auto-start removed. The crawler will no longer start on boot.
) else (
    echo.
    echo Auto-start was not enabled.
)
echo.
pause
