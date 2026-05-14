@echo off
title OF-Scraper GUI
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    echo Run install.bat first or see the README for setup instructions.
    pause
    exit /b 1
)

python app.py
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start.
    echo Make sure you ran install.bat first.
    pause
)