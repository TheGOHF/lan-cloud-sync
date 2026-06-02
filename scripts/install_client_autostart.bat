@echo off
setlocal

set "TASK_NAME=LAN Cloud Sync Client Watcher"
set "SCRIPT_PATH=%~dp0start_client_watch_hidden.vbs"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "STARTUP_SCRIPT=%STARTUP_DIR%\lan-cloud-sync-client-watcher.vbs"

if not exist "%SCRIPT_PATH%" (
    echo Script not found: "%SCRIPT_PATH%"
    exit /b 1
)

schtasks /Create /F /TN "%TASK_NAME%" /SC ONLOGON /TR "wscript.exe ""%SCRIPT_PATH%""" /RL LIMITED
if not errorlevel 1 (
    echo Installed scheduled task: "%TASK_NAME%"
    exit /b 0
)

echo Scheduled task install failed. Falling back to the current user's Startup folder.
if not exist "%STARTUP_DIR%" (
    mkdir "%STARTUP_DIR%"
)

(
    echo Set shell = CreateObject("WScript.Shell"^)
    echo shell.Run "wscript.exe ""%SCRIPT_PATH%""", 0, False
) > "%STARTUP_SCRIPT%"

echo Installed Startup launcher: "%STARTUP_SCRIPT%"
exit /b 0
