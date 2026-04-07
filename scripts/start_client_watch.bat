@echo off
setlocal

set "ROOT_DIR=%~dp0.."
set "PYTHON_EXE=%ROOT_DIR%\client\venv\Scripts\python.exe"
set "LOG_DIR=%ROOT_DIR%\logs"
set "LOG_FILE=%LOG_DIR%\client-watch.log"

if "%~1"=="" (
    set "DEVICE_ID=pc-1"
) else (
    set "DEVICE_ID=%~1"
)

if not exist "%PYTHON_EXE%" (
    echo Client venv Python not found: "%PYTHON_EXE%"
    exit /b 1
)

if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
)

cd /d "%ROOT_DIR%\client"
"%PYTHON_EXE%" -m app.cli.main watch --device-id "%DEVICE_ID%" >> "%LOG_FILE%" 2>&1
exit /b %errorlevel%
