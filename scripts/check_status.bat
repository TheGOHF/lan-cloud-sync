@echo off
setlocal

set "ROOT_DIR=%~dp0.."
set "SERVER_LOG=%ROOT_DIR%\logs\server.log"
set "CLIENT_LOG=%ROOT_DIR%\logs\client-watch.log"
set "STATUS_LOG=%ROOT_DIR%\logs\check-status.log"

if not exist "%ROOT_DIR%\logs" (
    mkdir "%ROOT_DIR%\logs"
)

call :run_check > "%STATUS_LOG%" 2>&1
type "%STATUS_LOG%"
echo.
echo Full report saved to: "%STATUS_LOG%"
pause
exit /b 0

 :run_check
echo === LAN Cloud Sync Status ===
echo.

echo [Server TCP 8000]
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table -AutoSize"
echo.

echo [Python Processes]
tasklist /FI "IMAGENAME eq python.exe"
tasklist /FI "IMAGENAME eq pythonw.exe"
echo.

echo [Server Health Check]
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/files -TimeoutSec 5; Write-Host ('Status: ' + [int]$r.StatusCode); Write-Host ('Body: ' + $r.Content) } catch { Write-Host $_.Exception.Message }"
echo.

echo [Recent Server Log]
if exist "%SERVER_LOG%" (
    powershell -NoProfile -Command "Get-Content '%SERVER_LOG%' -Tail 20"
) else (
    echo No server log found at "%SERVER_LOG%"
)
echo.

echo [Recent Client Log]
if exist "%CLIENT_LOG%" (
    powershell -NoProfile -Command "Get-Content '%CLIENT_LOG%' -Tail 20"
) else (
    echo No client log found at "%CLIENT_LOG%"
)

exit /b 0
