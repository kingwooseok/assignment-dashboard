@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, multipart, icalendar, tzdata" >nul 2>&1
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
)
echo.
echo Open http://127.0.0.1:8000 in your browser.
echo Press Ctrl+C to stop the server.
echo.
".venv\Scripts\python.exe" -X utf8 run.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Start failed. Check the message above.
pause
exit /b 1
