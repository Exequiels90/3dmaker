@echo off
setlocal enabledelayedexpansion

cd /d "c:\Users\PC-001-8325\Pictures\so"

REM Clean up old database
echo.
echo ========== DATABASE CLEANUP ==========
python cleanup_db.py
if %ERRORLEVEL% neq 0 (
    echo Error during cleanup. Exiting.
    pause
    exit /b 1
)

echo.
echo ========== STARTING FLASK APPLICATION ==========
echo.

REM Start Flask with force reset enabled
set FORCE_RESET_DB=true
python app.py

pause
