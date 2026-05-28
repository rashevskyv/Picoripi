@echo off

:: Check if the virtual environment folder exists
if not exist ".venv" (
    echo [ERROR] Virtual environment '.venv' not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

:: Activate the environment
echo Activating environment...
call .venv\Scripts\activate.bat

:: Run the main Python script
echo Starting the program...
python main.py

echo.