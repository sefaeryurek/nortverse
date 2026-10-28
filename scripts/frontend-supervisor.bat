@echo off
REM Nortverse - Frontend denetleyicisini baslatir (Gorev Zamanlayici "Frontend" gorevi, pencere acmadan).
REM Uretim sunucusu 127.0.0.1:3000; asil is frontend-supervisor.ps1 icinde, tek kopya calisir.
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0frontend-supervisor.ps1"
exit /b %errorlevel%
