@echo off
REM Nortverse - Gunluk pipeline: bulten + analiz + DB (Gorev Zamanlayici: 08:00, pencere acmadan)
REM PC 08:00'de kapaliysa acilinca kacirilan calisma hemen yapilir.

set PYTHONIOENCODING=utf-8
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGFILE=%ROOT%\scripts\logs\pipeline.log"
set "ERRORLOG=%ROOT%\scripts\logs\pipeline_errors.log"

call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 (
    echo [%date% %time%] HATA: Docker/PostgreSQL hazir degil, pipeline calismadi >> "%ERRORLOG%"
    exit /b 1
)

cd /d "%ROOT%\backend"
echo [%date% %time%] Pipeline basliyor... >> "%LOGFILE%"
python -m app.cli.main run-pipeline >> "%LOGFILE%" 2>&1
set EXITCODE=%errorlevel%

if %EXITCODE% equ 0 (
    echo [%date% %time%] Pipeline basarili tamamlandi >> "%LOGFILE%"
) else (
    echo [%date% %time%] HATA: Pipeline basarisiz (exit code: %EXITCODE%) >> "%LOGFILE%"
    echo [%date% %time%] HATA: Pipeline basarisiz (exit code: %EXITCODE%) >> "%ERRORLOG%"
)
exit /b %EXITCODE%
