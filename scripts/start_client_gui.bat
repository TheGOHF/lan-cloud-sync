@echo off
setlocal

rem Start the LAN Cloud Sync desktop GUI. The watcher is controlled inside the GUI.

set "ROOT_DIR=%~dp0.."
set "CLIENT_DIR=%ROOT_DIR%\client"
set "VENV_PYTHON=%CLIENT_DIR%\venv\Scripts\python.exe"

cd /d "%ROOT_DIR%"

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -m client.app.gui.main
    exit /b %errorlevel%
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m client.app.gui.main
    exit /b %errorlevel%
)

where python >nul 2>nul
if not errorlevel 1 (
    python -m client.app.gui.main
    exit /b %errorlevel%
)

echo No suitable Python executable was found.
echo Expected one of:
echo   "%VENV_PYTHON%"
echo   py -3
echo   python
exit /b 1
