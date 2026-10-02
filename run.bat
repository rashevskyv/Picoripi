@echo off
cd /d "%~dp0"

:: tasks.py starts main.py in the project's environment (.venv, then venv).
if not exist ".venv" if not exist "venv" (
    echo [ERROR] No virtual environment ^('.venv' or 'venv'^) found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

echo Starting the program...
python tasks.py run %*
if errorlevel 1 pause
