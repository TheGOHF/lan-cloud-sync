@echo off
setlocal

set "ROOT_DIR=%~dp0.."
set "PYTHON_EXE=%ROOT_DIR%\server\venv\Scripts\python.exe"
set "LOG_DIR=%ROOT_DIR%\logs"
set "LOG_FILE=%LOG_DIR%\server.log"

if not exist "%PYTHON_EXE%" (
    echo Server venv Python not found: "%PYTHON_EXE%"
    exit /b 1
)

if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
)

"%PYTHON_EXE%" --version >nul 2>> "%LOG_FILE%"
if errorlevel 1 (
    echo Server venv Python exists but cannot be started: "%PYTHON_EXE%" >> "%LOG_FILE%"
    echo Recreate the server venv and reinstall requirements. >> "%LOG_FILE%"
    echo Server venv Python exists but cannot be started: "%PYTHON_EXE%"
    echo Recreate the server venv and reinstall requirements.
    exit /b 1
)

cd /d "%ROOT_DIR%"
"%PYTHON_EXE%" -m server.app.cli.main serve >> "%LOG_FILE%" 2>&1
exit /b %errorlevel%
