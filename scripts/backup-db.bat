@echo off
REM Nortverse - Gunluk PostgreSQL yedegi (Gorev Zamanlayici: 07:00, pencere acmadan)
REM Son 7 yedegi tutar. Bozuk/kucuk yedek basarili sayilmaz.

set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGDIR=%ROOT%\scripts\logs"
set "LOGFILE=%LOGDIR%\backup.log"
set "BACKUP_DIR=%ROOT%\backups"
set MIN_BACKUP_SIZE=10485760

if not exist "%LOGDIR%" mkdir "%LOGDIR%"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 exit /b 1

REM Tarih (YYYY-MM-DD) — wmic Windows 11'de yok, PowerShell kullanilir
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "DATESTAMP=%%I"
set "BACKUP_FILE=%BACKUP_DIR%\nortverse_%DATESTAMP%.dump"

echo [%date% %time%] Yedekleme basliyor: %BACKUP_FILE% >> "%LOGFILE%"
pushd "%ROOT%"
docker compose exec -T db pg_dump -U nortverse -d nortverse --format=custom --compress=9 > "%BACKUP_FILE%" 2>> "%LOGFILE%"
set DUMPCODE=%errorlevel%
popd

set FSIZE=0
for %%A in ("%BACKUP_FILE%") do set FSIZE=%%~zA
if not "%DUMPCODE%"=="0" goto failed
if %FSIZE% LSS %MIN_BACKUP_SIZE% goto failed

echo [%date% %time%] Yedekleme basarili (%FSIZE% byte) >> "%LOGFILE%"
REM 7 gunden eski yedekleri sil
forfiles /p "%BACKUP_DIR%" /m "nortverse_*.dump" /d -7 /c "cmd /c del @path" 2>nul
exit /b 0

:failed
echo [%date% %time%] HATA: Yedekleme basarisiz (kod %DUMPCODE%, %FSIZE% byte) >> "%LOGFILE%"
call "%~dp0notify-error.bat" "Veritabani yedegi alinamadi - kod %DUMPCODE%"
exit /b 1
