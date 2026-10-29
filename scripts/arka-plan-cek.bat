@echo off
REM Nortverse - Bekleyen veri cekimleri, gunduz elle (gece gorevinin "LongJobs" isinin aynisi).
REM
REM 1. Gol dakikalari (anlik mac modeli Faz N icin - 2024-07'den beri biten maclar)
REM 2. Mac sonu oran gecmisi (Sprint 94 I1 - Subat 2026'dan beri)
REM
REM Cift tiklayin. Ikisi sirayla calisir, ayni anda degil. Kaldigi yerden devam eder; bitmisse aninda doner.
REM Gece 00:45'te kendiliginden durur - 01:00'deki gece gorevi ayni isi devralir, ikisi cakismaz.
REM Pencereyi kapatirsaniz durur; tekrar acinca devam eder.
REM Lig partisi dosyasi lig-partisi-cek.bat ile ayni anda calisabilir; mac saatlerinde ikisi de yavaslar.
REM Ayrinti: scripts\logs\goal_events.log ve scripts\logs\odds_ft.log

title Nortverse - Gol dakikalari ve oran gecmisi
set PYTHONIOENCODING=utf-8
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGFILE=%ROOT%\scripts\logs\goal_events.log"
set "ODDSLOG=%ROOT%\scripts\logs\odds_ft.log"

call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 (
    echo HATA: Docker veya veritabani hazir degil. Docker Desktop'i acip tekrar deneyin.
    pause
    exit /b 1
)

cd /d "%ROOT%\backend"
echo === 1/2 Gol dakikalari cekiliyor - ilerleme: scripts\logs\goal_events.log ===
echo [%date% %time%] Elle baslatildi - gol dakikalari >> "%LOGFILE%"
python -m app.cli.main backfill-goal-events --since 2024-07-01 --delay 6 --until 00:45 >> "%LOGFILE%" 2>&1
echo [%date% %time%] Gol dakikalari durdu - kod %errorlevel% >> "%LOGFILE%"

echo === 2/2 Mac sonu oran gecmisi cekiliyor - ilerleme: scripts\logs\odds_ft.log ===
echo [%date% %time%] Elle baslatildi - mac sonu oranlari >> "%ODDSLOG%"
python -m app.cli.main backfill-odds --scope ft --since 2026-02-01 --delay 6 --until 00:45 >> "%ODDSLOG%" 2>&1
echo [%date% %time%] Mac sonu oranlari durdu - kod %errorlevel% >> "%ODDSLOG%"

echo.
echo Durdu - ya is bitti ya saat 00:45 oldu. Gece gorevi kaldigi yerden devam eder.
pause
exit /b 0
