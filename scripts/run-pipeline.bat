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
    call "%~dp0notify-error.bat" "Sabah pipeline calismadi - Docker/PostgreSQL hazir degil"
    exit /b 1
)

call "%~dp0wait-network.bat" "%LOGFILE%"
if errorlevel 1 (
    echo [%date% %time%] HATA: Ag hazir degil, pipeline calismadi >> "%ERRORLOG%"
    call "%~dp0notify-error.bat" "Sabah pipeline calismadi - veri kaynagina baglanilamadi"
    exit /b 1
)

cd /d "%ROOT%\backend"
echo [%date% %time%] Pipeline basliyor... >> "%LOGFILE%"
python -m app.cli.main run-pipeline >> "%LOGFILE%" 2>&1
set EXITCODE=%errorlevel%
if %EXITCODE% equ 0 goto ok

REM Gecici ag/kaynak hatasi olabilir: 10 dk sonra bir kez daha - kayitlar idempotent, ikinci calisma zarar vermez
echo [%date% %time%] Pipeline basarisiz - kod %EXITCODE%, 10 dk sonra tekrar denenecek >> "%LOGFILE%"
ping -n 601 127.0.0.1 >nul
call "%~dp0wait-network.bat" "%LOGFILE%"
echo [%date% %time%] Pipeline ikinci deneme basliyor... >> "%LOGFILE%"
python -m app.cli.main run-pipeline >> "%LOGFILE%" 2>&1
set EXITCODE=%errorlevel%
if %EXITCODE% equ 0 goto ok

echo [%date% %time%] HATA: Pipeline basarisiz - exit code %EXITCODE% >> "%LOGFILE%"
echo [%date% %time%] HATA: Pipeline basarisiz - exit code %EXITCODE% >> "%ERRORLOG%"
call "%~dp0notify-error.bat" "Sabah pipeline iki denemede de basarisiz - kod %EXITCODE%, scripts\logs\pipeline.log"
exit /b %EXITCODE%

:ok
echo [%date% %time%] Pipeline basarili tamamlandi >> "%LOGFILE%"
exit /b 0
