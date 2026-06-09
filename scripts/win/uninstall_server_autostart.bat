@echo off
setlocal

schtasks /Delete /F /TN "LAN Cloud Sync Server"
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\lan-cloud-sync-server.vbs" (
    del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\lan-cloud-sync-server.vbs"
)
exit /b 0
