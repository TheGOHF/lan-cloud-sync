@echo off
setlocal

set "PID_FILE=%LOCALAPPDATA%\lan-cloud-sync\server.pid"

if not exist "%PID_FILE%" (
    echo PID file not found. Сервер не запущен через start_server.bat?
    exit /b 1
)

set /p PID=<"%PID_FILE%"

powershell -NoProfile -Command ^
  "$pid = %PID%; " ^
  "try { $proc = Get-Process -Id $pid -ErrorAction Stop; Stop-Process -Id $pid -Force; Write-Host ('Stopped server PID ' + $pid) } " ^
  "catch { Write-Host ('Server PID ' + $pid + ' not found (already stopped). Cleaning up PID file.') }; " ^
  "Remove-Item -LiteralPath \"%PID_FILE%\" -Force -ErrorAction SilentlyContinue"

exit /b 0
