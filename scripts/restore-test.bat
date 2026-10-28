@echo off
REM Nortverse - Aylik yedek geri yukleme testi (Sprint 94 D3; Gorev Zamanlayici: her ayin 1'i 10:00).
REM Bir yedek ancak geri yuklenebiliyorsa yedektir: en son dump GECICI bir konteynere (127.0.0.1:5544)
REM yuklenir, tablo sayilari canli veritabaniyla karsilastirilir, konteyner silinir. Canli DB'ye dokunulmaz.

setlocal EnableDelayedExpansion
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGFILE=%ROOT%\scripts\logs\backup.log"
set "BACKUP_DIR=%ROOT%\backups"
set "TEST_NAME=nortverse-restore-test"

call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 exit /b 1

set "LATEST="
for /f "delims=" %%F in ('dir /b /o-d "%BACKUP_DIR%\nortverse_*.dump" 2^>nul') do if not defined LATEST set "LATEST=%%F"
if not defined LATEST (
    echo [%date% %time%] HATA: Geri yukleme testi - yedek dosyasi yok >> "%LOGFILE%"
    call "%~dp0notify-error.bat" "Geri yukleme testi yapilamadi - yedek dosyasi yok"
    exit /b 1
)
echo [%date% %time%] Geri yukleme testi basliyor: %LATEST% >> "%LOGFILE%"

docker rm -f %TEST_NAME% >nul 2>&1
docker run -d --name %TEST_NAME% -e POSTGRES_USER=nortverse -e POSTGRES_PASSWORD=restoretest -e POSTGRES_DB=nortverse -p 127.0.0.1:5544:5432 postgres:16-alpine >> "%LOGFILE%" 2>&1
if errorlevel 1 goto failed
REM Konteyner hazir olana kadar bekle (en fazla ~1 dk; "timeout" gizli konsolda beklemez)
set READY=0
for /l %%i in (1,1,12) do (
    if !READY! equ 0 (
        ping -n 6 127.0.0.1 >nul
        docker exec %TEST_NAME% pg_isready -U nortverse -d nortverse >nul 2>&1 && set READY=1
    )
)
if %READY% equ 0 goto failed

docker cp "%BACKUP_DIR%\%LATEST%" %TEST_NAME%:/tmp/test.dump >> "%LOGFILE%" 2>&1
if errorlevel 1 goto failed
docker exec %TEST_NAME% pg_restore -U nortverse -d nortverse --no-owner --exit-on-error /tmp/test.dump >> "%LOGFILE%" 2>&1
if errorlevel 1 goto failed

REM Sayim: tahmin defteri degismez (sadece eklenir) -> yedekteki satir sayisi, canli DB'de yedegin son kayit anina
REM kadar yazilmis satir sayisina BIREBIR esit olmali. matches tablosu arsiv eklendikce buyur; sadece alt sinir.
for /f "tokens=1,2,3" %%a in ('docker exec %TEST_NAME% psql -U nortverse -d nortverse -At -F " " -c "SELECT count(*), (SELECT count(*) FROM matches), coalesce(ceil(extract(epoch FROM max(recorded_at)))::bigint, 0) FROM prediction_ledger"') do (
    set "R_LEDGER=%%a" & set "R_MATCHES=%%b" & set "R_MAXREC=%%c"
)
if not defined R_MAXREC goto failed
pushd "%ROOT%"
for /f "tokens=1,2" %%a in ('docker compose exec -T db psql -U nortverse -d nortverse -At -F " " -c "SELECT count(*) FILTER (WHERE recorded_at <= to_timestamp(!R_MAXREC!)), (SELECT count(*) FROM matches) FROM prediction_ledger"') do (
    set "L_LEDGER=%%a" & set "L_MATCHES=%%b"
)
popd
echo [%date% %time%] Geri yukleme sayimi: defter yedek=%R_LEDGER% canli=%L_LEDGER% - maclar yedek=%R_MATCHES% canli=%L_MATCHES% >> "%LOGFILE%"
if not "%R_LEDGER%"=="%L_LEDGER%" goto failed
set /a MIN_MATCHES=L_MATCHES*80/100
if %R_MATCHES% LSS %MIN_MATCHES% goto failed
if %R_MATCHES% GTR %L_MATCHES% goto failed

docker rm -f %TEST_NAME% >nul 2>&1
echo [%date% %time%] Geri yukleme testi BASARILI >> "%LOGFILE%"
exit /b 0

:failed
docker rm -f %TEST_NAME% >nul 2>&1
echo [%date% %time%] HATA: Geri yukleme testi basarisiz - ayrinti yukarida >> "%LOGFILE%"
call "%~dp0notify-error.bat" "Yedek geri yukleme testi basarisiz - scripts\logs\backup.log"
exit /b 1
