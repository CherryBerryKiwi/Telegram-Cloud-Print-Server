@echo off
setlocal

REM ============================================================
REM run_all.bat
REM Run at the same time:
REM   1) start.py
REM   2) telegram_listener.py
REM
REM Place this file in the same folder as start.py and telegram_listener.py
REM ============================================================

cd /d "%~dp0"

echo ============================================================
echo AUTO PRINT PDFtoPrinter + TELEGRAM LISTENER STARTER
echo Project folder: %CD%
echo ============================================================
echo.

if not exist "start.py" (
    echo [ERROR] start.py not found in folder:
    echo %CD%
    echo.
    pause
    exit /b 1
)

if not exist "telegram_listener.py" (
    echo [ERROR] telegram_listener.py not found in folder:
    echo %CD%
    echo.
    pause
    exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    ) else (
        echo [ERROR] Python not found.
        echo Please install Python or add Python to PATH.
        echo.
        pause
        exit /b 1
    )
)

echo Python command: %PYTHON_CMD%
echo.


echo Opening telegram_listener.py...
start "TELEGRAM LISTENER" cmd /k "%PYTHON_CMD% telegram_listener.py"
timeout /t 1 /nobreak >nul
echo Opening start.py...
start "AUTO PRINT - PDFtoPrinter" cmd /k "%PYTHON_CMD% start.py"


echo.
echo Started 2 separate processes.
echo You can close this window, but DO NOT close the 2 new windows if you still want the program to keep running.
echo.
pause

endlocal