@echo off
REM ================================================
REM Teams LLM Bot startup batch (Windows)
REM - Create virtualenv if missing
REM - Install dependencies from requirements.txt
REM - Launch FastAPI server via uvicorn
REM ================================================

SETLOCAL

REM Change directory to the location of this script
cd /d "%~dp0"

REM Virtual environment directory name
SET VENV_DIR=.venv

REM Show info about required Python version
echo [INFO] This project expects Python 3.10.x.

REM Create virtual environment if it does not exist
IF NOT EXIST "%VENV_DIR%" (
    echo [INFO] Creating Python virtual environment: %VENV_DIR%
    python -m venv "%VENV_DIR%"
)

REM Activate virtual environment
CALL "%VENV_DIR%\Scripts\activate.bat"

REM Install dependencies
echo [INFO] Installing dependencies from requirements.txt...
pip install -r requirements.txt

REM Launch application server
echo [INFO] Starting Teams LLM Bot server...
uvicorn src.bot.server:app --host 0.0.0.0 --port 3978 --reload

ENDLOCAL

pause
