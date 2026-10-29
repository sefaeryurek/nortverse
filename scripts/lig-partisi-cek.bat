@echo off
REM Nortverse - Yeni golge lig partisi arsivi (Sprint 94 P2, karar K16).
REM
REM Ligler (nowgoal lig no): England League Two (35), Czech First League (137), Dutch Eerste Divisie (17),
REM Greek Super League (32), Polish Ekstraklasa (6). Her lig icin 5 sezon: 2022-2023 ... 2026-2027.
REM
REM Cift tiklayin. Pencere acik kaldigi surece calisir; kapatirsaniz durur.
REM Tekrar calistirinca BITEN SEZONLARI ATLAR, kaldigi sezondan devam eder
REM (bitenler scripts\logs\league-batch-done.txt dosyasinda tutulur).
REM Sezon icinde de zaten veritabaninda olan maclar tekrar cekilmez.
REM Sezonlar eskiden yeniye cekilir: her macin arsivi, o mactan onceki sezonlar hazirken hesaplanir.
REM Mac saatlerinde (hafta ici 19:00-00:30, hafta sonu 13:00-00:30) cekim kendiliginden yavaslar.
REM
REM Sure: tahminen 8-11 saat. Hepsi bitince takim gucu ve bu liglerin arsiv eslesmeleri hesaplanir.
REM Bu ligler henuz EKRANA ve deftere girmez; bitince Claude'a haber verin - golge listesine o ekler.
REM Ayrinti: scripts\logs\league_batch.log

title Nortverse - Yeni lig partisi arsivi
set PYTHONIOENCODING=utf-8
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGFILE=%ROOT%\scripts\logs\league_batch.log"
set "DONEFILE=%ROOT%\scripts\logs\league-batch-done.txt"
if not exist "%ROOT%\scripts\logs" mkdir "%ROOT%\scripts\logs"
if not exist "%DONEFILE%" type nul > "%DONEFILE%"

call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 (
    echo HATA: Docker veya veritabani hazir degil. Docker Desktop'i acip tekrar deneyin.
    pause
    exit /b 1
)

cd /d "%ROOT%\backend"
echo [%date% %time%] Lig partisi arsivi basliyor >> "%LOGFILE%"
set FAILED=0

REM ---- Ingiltere League Two (35) ----
for %%S in (2022-2023 2023-2024 2024-2025 2025-2026 2026-2027) do call :season 35 %%S "Ingiltere League Two"
REM ---- Cekya 1. Lig (137) ----
for %%S in (2022-2023 2023-2024 2024-2025 2025-2026 2026-2027) do call :season 137 %%S "Cekya"
REM ---- Hollanda Eerste Divisie (17) ----
for %%S in (2022-2023 2023-2024 2024-2025 2025-2026 2026-2027) do call :season 17 %%S "Hollanda Eerste Divisie"
REM ---- Yunanistan Super Lig (32) ----
for %%S in (2022-2023 2023-2024 2024-2025 2025-2026 2026-2027) do call :season 32 %%S "Yunanistan"
REM ---- Polonya Ekstraklasa (6) ----
for %%S in (2022-2023 2023-2024 2024-2025 2025-2026 2026-2027) do call :season 6 %%S "Polonya"

if not %FAILED% equ 0 (
    echo.
    echo UYARI: %FAILED% sezon tamamlanamadi. Dosyayi tekrar calistirin - sadece eksikler cekilir.
    echo Takim gucu ve arsiv eslesmeleri tum sezonlar bitince hesaplanacak.
    echo [%date% %time%] %FAILED% sezon eksik, son adimlar ertelendi >> "%LOGFILE%"
    pause
    exit /b 1
)

echo.
echo === Tum sezonlar tamam. Takim gucu hesaplaniyor... ===
echo [%date% %time%] Takim gucu hesaplaniyor >> "%LOGFILE%"
python -m app.cli.main backfill-team-lambdas >> "%LOGFILE%" 2>&1
echo === Bu liglerin arsiv eslesmeleri hesaplaniyor... ===
echo [%date% %time%] Arsiv eslesmeleri hesaplaniyor >> "%LOGFILE%"
python -m app.cli.main recompute-patterns --include-finished --league "England League Two" --league "Czech First League" --league "Dutch Eerste Divisie" --league "Greek Super League" --league "Polish Ekstraklasa" >> "%LOGFILE%" 2>&1
echo [%date% %time%] Lig partisi arsivi BITTI >> "%LOGFILE%"
>>"%DONEFILE%" echo BITTI
echo.
echo BITTI. Claude'a "lig partisi bitti" deyin. Ayrintilar: scripts\logs\league_batch.log
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
    set /a FAILED+=1
    goto :eof
)
>>"%DONEFILE%" echo %1 %2
echo [tamam] %~3 %2
goto :eof
