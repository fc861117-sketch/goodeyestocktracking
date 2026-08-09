@echo off
:: Gooaye Stock Analyzer - Scheduled Task Wrapper
:: Runs via Windows Task Scheduler / Antigravity.

set PYTHONIOENCODING=utf-8

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

if not exist "%SCRIPT_DIR%data" mkdir "%SCRIPT_DIR%data"

echo [%date% %time%] Starting Gooaye Stock Update...
python "%SCRIPT_DIR%cron_update.py" >> "%SCRIPT_DIR%data\scheduler_run.log" 2>&1
echo [%date% %time%] Done.
