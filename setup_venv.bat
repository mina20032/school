@echo off
REM Create virtual environment and install dependencies for Quiz Platform
cd /d "%~dp0"

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create venv. Ensure Python is installed and in PATH.
        exit /b 1
    )
)

echo Installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Done. To run the app:
echo   venv\Scripts\activate
echo   python app.py
echo.
echo In VS Code/Cursor: Select interpreter quiz_platform\venv\Scripts\python.exe
