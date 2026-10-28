@echo off
REM Nortverse - Backend denetleyicisini baslatir (Gorev Zamanlayici "Backend" gorevi, pencere acmadan).
REM Asil is backend-supervisor.ps1 icinde; tek kopya calisir, sik tetiklenmesi sorun degil.
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0backend-supervisor.ps1"
exit /b %errorlevel%
