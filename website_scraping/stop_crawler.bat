@echo off
:: Stops any running background auto_news_crawler instances
echo Stopping any active auto_news_crawler background processes...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*auto_news_crawler.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host 'Stopped PID:' $_.ProcessId }"
echo Done.
pause
