@echo off
echo Building Kototsuna...

REM Check if Python exists
if not exist ".venv\Scripts\python.exe" (
    echo Error: Python executable not found at .venv\Scripts\python.exe
    echo Please make sure the virtual environment is set up correctly.
    pause
    exit /b
)

REM Check Python version
echo Using Python at: .venv\Scripts\python.exe
.venv\Scripts\python.exe --version

REM Run PyInstaller
echo Running PyInstaller...
.venv\Scripts\python.exe -m PyInstaller --noconfirm Kototsuna.spec

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo !!!!      BUILD FAILED          !!!!
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    echo Please check the error messages above.
) else (
    echo.
    echo Build complete! Check the 'dist' folder.
)

pause