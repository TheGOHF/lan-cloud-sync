@echo off
setlocal

rem Starts the background CLI watcher. Device id and sync folder come from the client config.

set "ROOT_DIR=%~dp0.."
set "PYTHON_EXE=%ROOT_DIR%\client\venv\Scripts\python.exe"
set "LOG_DIR=%ROOT_DIR%\logs"
set "LOG_FILE=%LOG_DIR%\client-watch.log"

set "DEVICE_ID="
if not "%~1"=="" (
    set "DEVICE_ID=%~1"
)

if not exist "%PYTHON_EXE%" (
    echo Client venv Python not found: "%PYTHON_EXE%"
    exit /b 1
)

if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
)

"%PYTHON_EXE%" --version >nul 2>> "%LOG_FILE%"
if errorlevel 1 (
    echo Client venv Python exists but cannot be started: "%PYTHON_EXE%" >> "%LOG_FILE%"
    echo Recreate the client venv and reinstall requirements. >> "%LOG_FILE%"
    echo Client venv Python exists but cannot be started: "%PYTHON_EXE%"
    echo Recreate the client venv and reinstall requirements.
    exit /b 1
)

cd /d "%ROOT_DIR%\client"
if "%DEVICE_ID%"=="" (
    "%PYTHON_EXE%" -m app.cli.main watch >> "%LOG_FILE%" 2>&1
) else (
    "%PYTHON_EXE%" -m app.cli.main watch --device-id "%DEVICE_ID%" >> "%LOG_FILE%" 2>&1
)
exit /b %errorlevel%
