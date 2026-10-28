@echo off
REM Nortverse - Gece uzun isleri (Gorev Zamanlayici "LongJobs": 01:00, en gec 12:00'de kendiliginden biter).
REM Sprint 94 D5: uzun isler canli operasyonla (skor guncelleme, devre arasi kayitlari) yarismasin diye gece
REM calisir; isler sirayla, ayni anda degil. Her is kaldigi yerden devam eder; bitmisse aninda doner.
REM Kaynak hatasinda isler durmaz, artan aralikla bekler. Ayrinti: scripts\logs\goal_events.log

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
echo [%date% %time%] Gece isleri bitti - kod %EXITCODE% >> "%LOGFILE%"
if not %EXITCODE% equ 0 call "%~dp0notify-error.bat" "Gece isi - gol dakikalari - basarisiz, kod %EXITCODE%, scripts\logs\goal_events.log"
exit /b %EXITCODE%
