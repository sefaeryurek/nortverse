@echo off
REM Nortverse - telefona bildirim (ntfy.sh, Sprint 94 D4). notify-error.bat cagirir.
REM scripts\alerts.local.env icinde NTFY_TOPIC yoksa hicbir sey yapmaz.
setlocal
set "CFG=%~dp0alerts.local.env"
if not exist "%CFG%" exit /b 0
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%CFG%") do set "%%a=%%b"
if "%NTFY_TOPIC%"=="" exit /b 0
curl -fsS -m 10 --retry 2 -o nul -H "Title: Nortverse" -H "Tags: warning" -d "%~1" "https://ntfy.sh/%NTFY_TOPIC%" >nul 2>&1
exit /b 0
