@echo off
setlocal

set "MATCH=-m app.cli.main watch"

powershell -NoProfile -Command ^
  "$targets = Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -like '*%MATCH%*' }; " ^
  "if (-not $targets) { Write-Host 'Client watch process not found.'; exit 0 }; " ^
  "$targets | ForEach-Object { Write-Host ('Stopping client PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force }"

exit /b %errorlevel%
