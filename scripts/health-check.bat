@echo off
REM Nortverse - saglik kontrolu (Gorev Zamanlayici "HealthCheck", 11:00-01:30 arasi 15 dk'da bir, pencere acmadan)
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0health-check.ps1"
exit /b %errorlevel%
