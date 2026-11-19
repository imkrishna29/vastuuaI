@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -m venv .venv
  if errorlevel 1 (echo Python not found. Install Python 3.11+ & pause & exit /b 1)
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (echo Installation failed. & pause & exit /b 1)
echo Open http://127.0.0.1:8000 in your browser
.venv\Scripts\python.exe app.py
pause
