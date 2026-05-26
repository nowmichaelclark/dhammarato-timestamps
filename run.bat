@echo off
REM run.bat — One-click launcher for the timestamp finder (Windows).
REM Usage: Double-click this file, or run it from a Command Prompt.

cd /d "%~dp0"

REM ── 1. Check for Python ─────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+ from python.org
    pause
    exit /b 1
)

REM ── 2. Create venv if missing ───────────────────────────────────────────
if not exist ".venv\" (
    echo Creating virtual environment ...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

REM ── 3. Install / upgrade dependencies ───────────────────────────────────
echo Checking dependencies ...
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

REM ── 4. Run ──────────────────────────────────────────────────────────────
python main.py

pause
