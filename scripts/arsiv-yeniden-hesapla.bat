@echo off
REM Nortverse - Arsiv eslesmelerini yeni algoritmayla yeniden hesapla (Sprint 94 B5 + B6, K19).
REM
REM Arsiv algoritmasi b3 / c5 / d5 oldu: ilk yari ve 2. yari arsivlerinde "sadece mac sonu" alanlari artik bos
REM (eskiden sahte %0 yaziliyordu) ve saati aciklanmamis maclar ayni gunun sonrasina aday olmuyor.
REM Yaklasan maclar okunurken zaten kendiliginden yenilenir; bu dosya BITMIS maclarin saklanmis degerlerini de
REM yeniler (gecmis karsilastirmalar icin). Defterdeki gercek kayitlar degismez.
REM
REM Cift tiklayin. Sure: 1 saatten fazla (yaklasik 44 bin mac). Pencereyi kapatirsaniz durur; tekrar
REM calistirinca sadece henuz yenilenmemis maclari isler. Mac saatleri disinda calistirmaniz onerilir.
REM Ayrinti: scripts\logs\recompute.log

title Nortverse - Arsiv yeniden hesaplama
set PYTHONIOENCODING=utf-8
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGFILE=%ROOT%\scripts\logs\recompute.log"
if not exist "%ROOT%\scripts\logs" mkdir "%ROOT%\scripts\logs"

call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 (
    echo HATA: Docker veya veritabani hazir degil. Docker Desktop'i acip tekrar deneyin.
    pause
    exit /b 1
)

cd /d "%ROOT%\backend"
echo === Veritabani guncellemesi uygulaniyor... ===
python -m alembic upgrade head >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo HATA: Veritabani guncellemesi uygulanamadi. Ayrinti: scripts\logs\recompute.log
    pause
    exit /b 1
)
echo === Arsiv eslesmeleri yeniden hesaplaniyor - uzun surer... ===
echo [%date% %time%] recompute-patterns --stale-only --include-finished basliyor >> "%LOGFILE%"
python -m app.cli.main recompute-patterns --stale-only --include-finished >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo HATA: Yeniden hesaplama yarida kaldi. Tekrar calistirin - kaldigi yerden devam eder.
    echo [%date% %time%] HATA recompute >> "%LOGFILE%"
    pause
    exit /b 1
)
echo [%date% %time%] Yeniden hesaplama BITTI >> "%LOGFILE%"
echo.
echo BITTI. Ayrintilar: scripts\logs\recompute.log
pause
exit /b 0
