@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m pip install --upgrade pip
    py -3 -m pip install websocket-client python-telegram-bot pypdf
) else (
    python -m pip install --upgrade pip
    python -m pip install websocket-client python-telegram-bot pypdf
)
pause
endlocal
