@echo off
REM Nortverse - Gunluk PostgreSQL yedekleme
REM Task Scheduler ile her sabah 07:00'de calistirilir
REM Son 7 yedegi tutar, eskileri siler

set LOGFILE=C:\Users\Sefa\Desktop\NORTVERSE - CODEX\scripts\logs\backup.log
set BACKUP_DIR=C:\Users\Sefa\Desktop\NORTVERSE - CODEX\backups

REM Backup klasoru yoksa olustur
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Docker PostgreSQL kontrolu
docker ps --filter "name=nortverse" --format "{{.Names}}" | findstr /i "nortverse" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] Docker PostgreSQL calismyor, baslatiliyor... >> "%LOGFILE%"
    cd /d "C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
    docker compose up -d >> "%LOGFILE%" 2>&1
    timeout /t 5 /nobreak >nul
)

REM Tarih formatini olustur (YYYY-MM-DD)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set DATESTAMP=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%

set BACKUP_FILE=%BACKUP_DIR%\nortverse_%DATESTAMP%.sql

echo [%date% %time%] Yedekleme basliyor... >> "%LOGFILE%"

REM pg_dump ile yedek al (Docker container icindeki pg_dump kullanilir)
docker exec nortverse-db-1 pg_dump -U nortverse -d nortverse > "%BACKUP_FILE%" 2>> "%LOGFILE%"

if %errorlevel% equ 0 (
    echo [%date% %time%] Yedekleme basarili: %BACKUP_FILE% >> "%LOGFILE%"
) else (
    echo [%date% %time%] HATA: Yedekleme basarisiz (exit code: %errorlevel%) >> "%LOGFILE%"
    exit /b 1
)

REM 7 gunden eski yedekleri sil
forfiles /p "%BACKUP_DIR%" /m "nortverse_*.sql" /d -7 /c "cmd /c del @path" 2>nul
echo [%date% %time%] Eski yedekler temizlendi >> "%LOGFILE%"
