@echo off
setlocal

schtasks /Delete /F /TN "LAN Cloud Sync Client Watcher"
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\lan-cloud-sync-client-watcher.vbs" (
    del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\lan-cloud-sync-client-watcher.vbs"
)
exit /b 0
