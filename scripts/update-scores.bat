@echo off
REM Nortverse - Skor guncelleme + tahmin defteri cozumu (pencere acmadan)
REM Gorev Zamanlayici: 18:00-23:00 saat basi ve 00:30 (tek gorev - iki kopya paralel calismaz).
REM --pending-days 3: son 3 gunde sonucu eksik kalan gunleri de yakalar; sonunda defter cozulur.

set PYTHONIOENCODING=utf-8
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGFILE=%ROOT%\scripts\logs\scores.log"
set "ERRORLOG=%ROOT%\scripts\logs\scores_errors.log"

call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 (
    echo [%date% %time%] HATA: Docker/PostgreSQL hazir degil, skor guncellenmedi >> "%ERRORLOG%"
    call "%~dp0notify-error.bat" "Skor guncellenmedi - Docker/PostgreSQL hazir degil"
    exit /b 1
)

call "%~dp0wait-network.bat" "%LOGFILE%"
if errorlevel 1 (
    echo [%date% %time%] HATA: Ag hazir degil, skor guncellenmedi >> "%ERRORLOG%"
    call "%~dp0notify-error.bat" "Skor guncellenmedi - veri kaynagina baglanilamadi"
    exit /b 1
)

cd /d "%ROOT%\backend"
echo [%date% %time%] Skor guncelleme basliyor... >> "%LOGFILE%"
python -m app.cli.main update-scores --pending-days 3 >> "%LOGFILE%" 2>&1
set EXITCODE=%errorlevel%

REM Gunluk oran kaydi (Sprint 94 I2): son 2 gunde biten takip maclarinin MS + IY oran gecmisi (acilis, kapanis,
REM canli satirlar). Sadece eksik / mac bitmeden cekilmis olanlar; hatasi skor gorevini basarisiz saymaz.
python -m app.cli.main backfill-odds --days 2 --scope both --delay 3 >> "%ROOT%\scripts\logs\odds_daily.log" 2>&1

if %EXITCODE% equ 0 (
    echo [%date% %time%] Skor guncelleme basarili >> "%LOGFILE%"
    REM Saglik kontrolu icin basari isareti + olu adam ping'i
    type nul > "%ROOT%\scripts\logs\scores.ok"
    call "%~dp0hc-ping.bat" nortverse-skor
) else (
    echo [%date% %time%] HATA: Skor guncelleme basarisiz - exit code %EXITCODE% >> "%LOGFILE%"
    echo [%date% %time%] HATA: Skor guncelleme basarisiz - exit code %EXITCODE% >> "%ERRORLOG%"
    call "%~dp0notify-error.bat" "Skor guncelleme basarisiz - kod %EXITCODE%, scripts\logs\scores.log"
    call "%~dp0hc-ping.bat" nortverse-skor fail
)
exit /b %EXITCODE%
