@echo off
REM Nortverse - Gece uzun isleri (Gorev Zamanlayici "LongJobs": 01:00, en gec 12:00'de kendiliginden biter).
REM Sprint 94 D5: uzun isler canli operasyonla (skor guncelleme, devre arasi kayitlari) yarismasin diye gece
REM calisir; isler sirayla, ayni anda degil. Her is kaldigi yerden devam eder; bitmisse aninda doner.
REM Kaynak hatasinda isler durmaz, artan aralikla bekler. Sira: gol dakikalari, sonra mac sonu oran gecmisi.
REM Ayrinti: scripts\logs\goal_events.log ve scripts\logs\odds_ft.log

set PYTHONIOENCODING=utf-8
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGFILE=%ROOT%\scripts\logs\goal_events.log"

call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 exit /b 1
call "%~dp0wait-network.bat" "%LOGFILE%"
if errorlevel 1 exit /b 1

cd /d "%ROOT%\backend"
echo [%date% %time%] Gece isleri basliyor - gol dakikalari >> "%LOGFILE%"
python -m app.cli.main backfill-goal-events --since 2024-07-01 --delay 6 --until 12:00 >> "%LOGFILE%" 2>&1
set EXITCODE=%errorlevel%
echo [%date% %time%] Gol dakikalari bitti - kod %EXITCODE% >> "%LOGFILE%"
if not %EXITCODE% equ 0 call "%~dp0notify-error.bat" "Gece isi - gol dakikalari - basarisiz, kod %EXITCODE%, scripts\logs\goal_events.log"

REM Sprint 94 I1 - K11: mac sonu oran gecmisi Subat 2026'dan beri. Gol cekimi bitmeden sure dolduysa bu is
REM hemen cikar; gol cekimi erken bittiyse kalan surede calisir - iki is asla ayni anda degil.
set "ODDSLOG=%ROOT%\scripts\logs\odds_ft.log"
echo [%date% %time%] Gece isleri - mac sonu oranlari >> "%ODDSLOG%"
python -m app.cli.main backfill-odds --scope ft --since 2026-02-01 --delay 6 --until 12:00 >> "%ODDSLOG%" 2>&1
set ODDSCODE=%errorlevel%
echo [%date% %time%] Mac sonu oranlari bitti - kod %ODDSCODE% >> "%ODDSLOG%"
if not %ODDSCODE% equ 0 call "%~dp0notify-error.bat" "Gece isi - mac sonu oranlari - basarisiz, kod %ODDSCODE%, scripts\logs\odds_ft.log"
if not %EXITCODE% equ 0 exit /b %EXITCODE%
exit /b %ODDSCODE%
