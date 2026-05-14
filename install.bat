@echo off
title Installing OF-Scraper GUI dependencies
cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    echo.
    echo Download Python from: https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    echo After installing Python, run this file again.
    pause
    exit /b 1
)

echo Python found. Installing dependencies...
pip install -r requirements_gui.txt
echo.
echo Done! Run launch.bat to start the GUI.
pause