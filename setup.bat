@echo off
setlocal

:: Work in the folder of this file. Started with "Run as administrator" (or from a shortcut), the current folder is
:: C:\Windows\System32: .venv would be deleted and made there and requirements.txt would not be found.
cd /d "%~dp0"

if not exist "requirements.txt" goto no_requirements
if not exist "main.py" goto no_main

echo [SETUP] Folder: %CD%
echo [SETUP] Python in PATH:
python --version
if %ERRORLEVEL% neq 0 goto no_python

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
python -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

echo [SETUP] Setup completed successfully!
pause
exit /b 0

:no_requirements
echo [ERROR] requirements.txt was not found in "%CD%".
echo Unpack the whole Picoripi archive first, then start setup.bat from the unpacked folder.
pause
exit /b 1

:no_main
echo [ERROR] main.py was not found in "%CD%". setup.bat must stay in the Picoripi folder.
pause
exit /b 1

:no_python
echo [ERROR] Python was not found. Install Python 3.14 and tick "Add python.exe to PATH".
pause
exit /b 1
