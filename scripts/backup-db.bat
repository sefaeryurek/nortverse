@echo off
REM Nortverse - Gunluk PostgreSQL yedegi (Gorev Zamanlayici: 07:00, pencere acmadan)
REM C: uzerinde son 7 yedek, D:\NortverseYedek uzerinde son 30 yedek + .env kopyasi.
REM Bozuk/kucuk yedek basarili sayilmaz.

set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGDIR=%ROOT%\scripts\logs"
set "LOGFILE=%LOGDIR%\backup.log"
set "BACKUP_DIR=%ROOT%\backups"
set MIN_BACKUP_SIZE=10485760
set "MIRROR_ROOT=D:"
set "MIRROR=D:\NortverseYedek"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Uyanista pipeline ve skor gorevleriyle ayni anda DB'yi yormasin: 5 dk bekle ("timeout" gizli konsolda beklemez)
ping -n 301 127.0.0.1 >nul

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
REM 7 gunden eski yedekleri sil (C: SSD dolu)
forfiles /p "%BACKUP_DIR%" /m "nortverse_*.dump" /d -7 /c "cmd /c del @path" 2>nul

REM Ikinci disk kopyasi (D: ayri fiziksel disk): son 30 gun + git'e girmeyen .env dosyalari
REM .env dosyalari olmadan yedek geri yuklense bile sistem calismaz - DB sifresi, ic anahtar orada
if not exist "%MIRROR_ROOT%\" goto nomirror
if not exist "%MIRROR%" mkdir "%MIRROR%"
if not exist "%MIRROR%\env" mkdir "%MIRROR%\env"
robocopy "%BACKUP_DIR%" "%MIRROR%" "nortverse_%DATESTAMP%.dump" /NFL /NDL /NJH /NJS /R:2 /W:5 >nul
if errorlevel 8 goto mirrorfailed
copy /y "%ROOT%\backend\.env" "%MIRROR%\env\backend.env" >nul 2>&1
copy /y "%ROOT%\frontend\.env.local" "%MIRROR%\env\frontend.env.local" >nul 2>&1
forfiles /p "%MIRROR%" /m "nortverse_*.dump" /d -30 /c "cmd /c del @path" 2>nul
echo [%date% %time%] D: kopyasi tamam: %MIRROR% >> "%LOGFILE%"
call "%~dp0hc-ping.bat" nortverse-yedek
exit /b 0

:nomirror
echo [%date% %time%] UYARI: %MIRROR_ROOT% yok - ikinci disk kopyasi alinmadi >> "%LOGFILE%"
call "%~dp0notify-error.bat" "Yedek alindi ama D: diskine kopyalanamadi - disk bagli mi"
exit /b 0

:mirrorfailed
echo [%date% %time%] HATA: D: kopyasi basarisiz >> "%LOGFILE%"
call "%~dp0notify-error.bat" "Yedek D: diskine kopyalanamadi - scripts\logs\backup.log"
call "%~dp0hc-ping.bat" nortverse-yedek fail
exit /b 1

:failed
echo [%date% %time%] HATA: Yedekleme basarisiz (kod %DUMPCODE%, %FSIZE% byte) >> "%LOGFILE%"
call "%~dp0notify-error.bat" "Veritabani yedegi alinamadi - kod %DUMPCODE%"
call "%~dp0hc-ping.bat" nortverse-yedek fail
exit /b 1
