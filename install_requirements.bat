@echo off
setlocal
echo ========================================
echo      Setting up Environment for Windows
echo ========================================

REM 1. Check for Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in your PATH.
    echo Please install Python for Windows from python.org
    pause
    exit /b
)

REM 2. Remove broken .venv if it exists
if exist ".venv" (
    echo Removing incompatible virtual environment...
    rmdir /s /q .venv
)

REM 3. Create new virtual environment
echo Creating new virtual environment (.venv)...
python -m venv .venv
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to create virtual environment.
    pause
    exit /b
)

REM 4. Install dependencies
echo.
echo Installing requirements...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install pyinstaller

echo.
echo ========================================
echo        Setup Complete!
echo ========================================
echo You can now run build.bat
pause
