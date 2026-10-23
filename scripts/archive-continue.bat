@echo off
REM Nortverse - Ana liglerin eksik eski sezonlarini ceker (Sprint 53'te yarim kalan "7 lig x 24 sezon").
REM
REM Cift tiklayin. Pencere acik kaldigi surece calisir; kapatirsaniz durur.
REM Tekrar calistirinca BITEN SEZONLARI ATLAR, kaldigi sezondan devam eder
REM (bitenler scripts\logs\archive-done.txt dosyasinda tutulur).
REM Sezon icinde de zaten veritabaninda olan maclar tekrar cekilmez.
REM
REM Sure: ~41 sezon, tahminen 10-15 saat (gece calistirmak uygun).
REM Hepsi bitince takim gucu ve arsiv eslesmeleri otomatik hesaplanir.

title Nortverse - Arsiv tamamlama
set PYTHONIOENCODING=utf-8
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGFILE=%ROOT%\scripts\logs\archive.log"
set "DONEFILE=%ROOT%\scripts\logs\archive-done.txt"
if not exist "%DONEFILE%" type nul > "%DONEFILE%"

call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 (
    echo HATA: Docker veya veritabani hazir degil. Docker Desktop'i acip tekrar deneyin.
    pause
    exit /b 1
)

cd /d "%ROOT%\backend"
echo [%date% %time%] Arsiv tamamlama basliyor >> "%LOGFILE%"

REM ---- Almanya Bundesliga (8): 2003-04 ... 2010-11 ----
for %%S in (2010-2011 2009-2010 2008-2009 2007-2008 2006-2007 2005-2006 2004-2005 2003-2004) do call :season 8 %%S "Almanya"
REM ---- Hollanda Eredivisie (16): 2003-04 ... 2011-12 ----
for %%S in (2011-2012 2010-2011 2009-2010 2008-2009 2007-2008 2006-2007 2005-2006 2004-2005 2003-2004) do call :season 16 %%S "Hollanda"
REM ---- Fransa Ligue 1 (11): 2003-04 ... 2012-13 ----
for %%S in (2012-2013 2011-2012 2010-2011 2009-2010 2008-2009 2007-2008 2006-2007 2005-2006 2004-2005 2003-2004) do call :season 11 %%S "Fransa"
REM ---- Turkiye Super Lig (30): 2003-04 ... 2012-13 ----
for %%S in (2012-2013 2011-2012 2010-2011 2009-2010 2008-2009 2007-2008 2006-2007 2005-2006 2004-2005 2003-2004) do call :season 30 %%S "Turkiye"
REM ---- Ispanya La Liga (31) ve Italya Serie A (34): 2003-04, 2004-05 ----
for %%S in (2004-2005 2003-2004) do call :season 31 %%S "Ispanya"
for %%S in (2004-2005 2003-2004) do call :season 34 %%S "Italya"

echo.
echo === Tum sezonlar tamam. Takim gucu ve arsiv eslesmeleri hesaplaniyor... ===
echo [%date% %time%] Takim gucu hesaplaniyor >> "%LOGFILE%"
python -m app.cli.main backfill-team-lambdas >> "%LOGFILE%" 2>&1
echo [%date% %time%] Arsiv eslesmeleri hesaplaniyor >> "%LOGFILE%"
python -m app.cli.main recompute-patterns --stale-only --include-finished >> "%LOGFILE%" 2>&1
echo [%date% %time%] Arsiv tamamlama BITTI >> "%LOGFILE%"
echo.
echo BITTI. Ayrintilar: scripts\logs\archive.log
pause
exit /b 0

:season
REM %1 = nowgoal lig no, %2 = sezon, %3 = lig adi
findstr /x /c:"%1 %2" "%DONEFILE%" >nul
if not errorlevel 1 (
    echo [atlandi] %~3 %2 zaten tamam
    goto :eof
)
echo.
echo === %~3 %2 cekiliyor... ===
echo [%date% %time%] %~3 lig %1 sezon %2 basliyor >> "%LOGFILE%"
python -m app.cli.main build-archive %1 %2 --concurrency 3 >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo [HATA] %~3 %2 tamamlanamadi - tekrar calistirinca yeniden denenecek
    echo [%date% %time%] HATA: %~3 %2 kod %errorlevel% >> "%LOGFILE%"
    goto :eof
)
>>"%DONEFILE%" echo %1 %2
echo [tamam] %~3 %2
goto :eof
