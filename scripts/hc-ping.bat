@echo off
REM Nortverse - healthchecks.io ping'i (olu adam anahtari, Sprint 94 D4).
REM Kullanim: call "%~dp0hc-ping.bat" <kontrol-adi> [fail]
REM scripts\alerts.local.env icinde HC_PING_KEY yoksa hicbir sey yapmaz.
setlocal
set "CFG=%~dp0alerts.local.env"
if not exist "%CFG%" exit /b 0
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%CFG%") do set "%%a=%%b"
if "%HC_PING_KEY%"=="" exit /b 0
set "URL=https://hc-ping.com/%HC_PING_KEY%/%~1"
if /i "%~2"=="fail" set "URL=%URL%/fail"
curl -fsS -m 10 --retry 2 -o nul "%URL%?create=1" >nul 2>&1
exit /b 0
