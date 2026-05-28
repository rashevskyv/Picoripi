@echo off
setlocal

echo [SETUP] Deleting old virtual environment...
if exist ".venv" (
    rmdir /s /q ".venv"
    echo [SETUP] .venv deleted.
) else (
    echo [SETUP] No existing .venv found.
)

echo [SETUP] Creating new virtual environment with Python 3.14...
python -m venv .venv
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to create virtual environment. Ensure Python 3.14 is installed and in PATH.
    pause
    exit /b 1
)

echo [SETUP] Activating environment...
call .venv\Scripts\activate.bat

echo [SETUP] Installing dependencies from requirements.txt...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

echo [SETUP] Setup completed successfully!
pause
