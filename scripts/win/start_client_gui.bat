@echo off
setlocal

rem Start the LAN Cloud Sync desktop GUI. The watcher is controlled inside the GUI.

set "ROOT_DIR=%~dp0.."
set "CLIENT_DIR=%ROOT_DIR%\client"
set "VENV_PYTHON=%CLIENT_DIR%\venv\Scripts\python.exe"
set "LOG_DIR=%ROOT_DIR%\logs"
set "LOG_FILE=%LOG_DIR%\client-gui.log"

cd /d "%ROOT_DIR%"

if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
)

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" --version >nul 2>nul
    if errorlevel 1 (
        echo Client venv Python exists but cannot be started: "%VENV_PYTHON%"
        echo Recreate the client venv and reinstall requirements.
        pause
        exit /b 1
    )
    "%VENV_PYTHON%" -m client.app.gui.main >> "%LOG_FILE%" 2>&1
    set "EXIT_CODE=%errorlevel%"
    if not "%EXIT_CODE%"=="0" (
        echo Client GUI exited with code %EXIT_CODE%. See "%LOG_FILE%".
        pause
    )
    exit /b %EXIT_CODE%
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m client.app.gui.main >> "%LOG_FILE%" 2>&1
    set "EXIT_CODE=%errorlevel%"
    if not "%EXIT_CODE%"=="0" (
        echo Client GUI exited with code %EXIT_CODE%. See "%LOG_FILE%".
        pause
    )
    exit /b %EXIT_CODE%
)

where python >nul 2>nul
if not errorlevel 1 (
    python -m client.app.gui.main >> "%LOG_FILE%" 2>&1
    set "EXIT_CODE=%errorlevel%"
    if not "%EXIT_CODE%"=="0" (
        echo Client GUI exited with code %EXIT_CODE%. See "%LOG_FILE%".
        pause
    )
    exit /b %EXIT_CODE%
)

echo No suitable Python executable was found.
echo Expected one of:
echo   "%VENV_PYTHON%"
echo   py -3
echo   python
exit /b 1
