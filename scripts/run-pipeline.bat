@echo off
REM Nortverse - Gunluk pipeline (fetch + analiz + DB kayit)
REM Task Scheduler ile her sabah 08:00'de calistirilir

set PYTHONIOENCODING=utf-8
set LOGFILE=C:\Users\Sefa\Desktop\NORTVERSE - CODEX\scripts\logs\pipeline.log

cd /d "C:\Users\Sefa\Desktop\NORTVERSE - CODEX\backend"

REM Docker PostgreSQL kontrolu
docker ps --filter "name=nortverse" --format "{{.Names}}" | findstr /i "nortverse" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] Docker PostgreSQL calismyor, baslatiliyor... >> "%LOGFILE%"
    cd /d "C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
    docker compose up -d >> "%LOGFILE%" 2>&1
    timeout /t 5 /nobreak >nul
    cd /d "C:\Users\Sefa\Desktop\NORTVERSE - CODEX\backend"
)

echo [%date% %time%] Pipeline basliyor... >> "%LOGFILE%"
python -m app.cli.main run-pipeline >> "%LOGFILE%" 2>&1
echo [%date% %time%] Pipeline tamamlandi (exit code: %errorlevel%) >> "%LOGFILE%"
