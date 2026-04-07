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

cd /d "%ROOT_DIR%"
"%PYTHON_EXE%" -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000 >> "%LOG_FILE%" 2>&1
exit /b %errorlevel%
