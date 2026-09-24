@echo off
REM Nortverse - Skor guncelleme (biten maclarin skorlarini ceker)
REM Task Scheduler ile 22:00 ve 00:30'da calistirilir

set PYTHONIOENCODING=utf-8
cd /d "C:\Users\Sefa\Desktop\NORTVERSE - CODEX\backend"

REM Docker PostgreSQL kontrolu
docker ps --filter "name=nortverse" --format "{{.Names}}" | findstr /i "nortverse" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] Docker PostgreSQL calismyor, baslatiliyor...
    cd /d "C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
    docker compose up -d
    timeout /t 5 /nobreak >nul
    cd /d "C:\Users\Sefa\Desktop\NORTVERSE - CODEX\backend"
)

echo [%date% %time%] Skor guncelleme basliyor...
python -m app.cli.main update-scores
echo [%date% %time%] Skor guncelleme tamamlandi (exit code: %errorlevel%)
