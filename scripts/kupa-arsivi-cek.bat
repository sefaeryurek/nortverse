@echo off
REM Nortverse - Avrupa kupalari arsivi (Sprint 94 P4, karar K17 secenek B).
REM
REM UEFA Sampiyonlar Ligi (103), Avrupa Ligi (113), Konferans Ligi (2187): lig / grup asamasi maclarinin
REM ilk yari ve 90 dakika skoru, son 5 sezon. Kupa basina sezon basina tek dosya cekilir: birkac dakika surer.
REM Once veritabani guncellemesi uygulanir (yeni tablo: cup_results). Tekrar calistirilabilir.
REM
REM Bu arsivi sadece canli golge kural live-cup-cond-v1 kullanir; ana liglerin oranlarina hicbir etkisi yok.
REM Ayrinti: scripts\logs\cup_archive.log

title Nortverse - Kupa arsivi
set PYTHONIOENCODING=utf-8
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGFILE=%ROOT%\scripts\logs\cup_archive.log"
if not exist "%ROOT%\scripts\logs" mkdir "%ROOT%\scripts\logs"

call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 (
    echo HATA: Docker veya veritabani hazir degil. Docker Desktop'i acip tekrar deneyin.
    pause
    exit /b 1
)

cd /d "%ROOT%\backend"
echo === Veritabani guncellemesi uygulaniyor... ===
echo [%date% %time%] alembic upgrade head >> "%LOGFILE%"
python -m alembic upgrade head >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo HATA: Veritabani guncellemesi uygulanamadi. Ayrinti: scripts\logs\cup_archive.log
    pause
    exit /b 1
)

echo === Kupa arsivi cekiliyor - 3 kupa x 5 sezon... ===
echo [%date% %time%] build-cup-archive basliyor >> "%LOGFILE%"
python -m app.cli.main build-cup-archive --seasons 5 >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo HATA: Kupa arsivi cekilemedi - kaynak yanit vermemis olabilir. Tekrar calistirin.
    echo [%date% %time%] HATA build-cup-archive >> "%LOGFILE%"
    pause
    exit /b 1
)
echo [%date% %time%] Kupa arsivi BITTI >> "%LOGFILE%"
echo.
echo BITTI. Ayrintilar: scripts\logs\cup_archive.log
pause
exit /b 0
