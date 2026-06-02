@echo off
setlocal

set "ROOT_DIR=%~dp0.."
set "PYTHON_EXE=%ROOT_DIR%\server\venv\Scripts\python.exe"

if "%~1"=="" (
    set "OLDER_THAN_DAYS=30"
) else (
    set "OLDER_THAN_DAYS=%~1"
)

if not exist "%PYTHON_EXE%" (
    echo Server venv Python not found: "%PYTHON_EXE%"
    exit /b 1
)

cd /d "%ROOT_DIR%"
"%PYTHON_EXE%" -m server.app.cli.main prune-tombstones --older-than-days "%OLDER_THAN_DAYS%"
exit /b %errorlevel%
