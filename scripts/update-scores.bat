@echo off
REM Nortverse - Skor guncelleme (biten maclarin skorlarini ceker)
REM Task Scheduler ile 22:00 ve 00:30'da calistirilir

set PYTHONIOENCODING=utf-8
set LOGFILE=C:\Users\Sefa\Desktop\NORTVERSE - CODEX\scripts\logs\scores.log

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

echo [%date% %time%] Skor guncelleme basliyor... >> "%LOGFILE%"
python -m app.cli.main update-scores >> "%LOGFILE%" 2>&1
echo [%date% %time%] Skor guncelleme tamamlandi (exit code: %errorlevel%) >> "%LOGFILE%"
