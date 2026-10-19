@echo off
REM Nortverse - Backend sunucusu (oturum acilisinda, pencere acmadan calisir).
REM Canli devre arasi kayitlari icin backend acik olmali. Cokerse 30 sn sonra yeniden baslatir;
REM 5 kez ust uste cokerse durur ve ekranda uyari gosterir.

set PYTHONIOENCODING=utf-8
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGFILE=%ROOT%\scripts\logs\backend.log"

REM Zaten calisiyorsa ikinci kopya acma (port 8000 dinleniyor mu?)
netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul
if not errorlevel 1 (
    REM Calisan sunucu backend.log dosyasini kilitli tutar; bu bilgi ayri dosyaya yazilir
    echo [%date% %time%] Backend zaten calisiyor - port 8000, yeni kopya acilmadi >> "%ROOT%\scripts\logs\backend_starts.log"
    exit /b 0
)

REM Log 20 MB'i gecerse eskiyi sakla, yenisine basla
for %%A in ("%LOGFILE%") do if %%~zA GTR 20000000 move /y "%LOGFILE%" "%ROOT%\scripts\logs\backend.old.log" >nul

call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 (
    call "%~dp0notify-error.bat" "Backend baslatilamadi - Docker/PostgreSQL hazir degil"
    exit /b 1
)

cd /d "%ROOT%\backend"
set CRASHES=0

:loop
REM Arada elle baska bir sunucu acildiysa tekrar baslatma - yoksa 5 basarisiz deneme yanlis uyari verir
netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul
if not errorlevel 1 (
    echo [%date% %time%] Port 8000 baska bir sunucuda, yeniden baslatma yapilmadi >> "%ROOT%\scripts\logs\backend_starts.log"
    exit /b 0
)
REM Log 20 MB'i gectiyse her yeniden baslatmada da dondurulur
for %%A in ("%LOGFILE%") do if %%~zA GTR 20000000 move /y "%LOGFILE%" "%ROOT%\scripts\logs\backend.old.log" >nul
for /f %%T in ('powershell -NoProfile -Command "[DateTimeOffset]::Now.ToUnixTimeSeconds()"') do set STARTED=%%T
echo [%date% %time%] Backend basliyor >> "%LOGFILE%"
python -m app.cli.main serve >> "%LOGFILE%" 2>&1
set EXITCODE=%errorlevel%
for /f %%T in ('powershell -NoProfile -Command "[DateTimeOffset]::Now.ToUnixTimeSeconds()"') do set STOPPED=%%T
set /a UPTIME=STOPPED-STARTED
REM 10 dakikadan uzun calistiysa tek bir cokme sayilir; seyrek yeniden baslatmalar gun boyu birikmesin
if %UPTIME% GEQ 600 set CRASHES=0
set /a CRASHES+=1
echo [%date% %time%] Backend durdu - kod %EXITCODE%, %UPTIME% sn calisti, deneme %CRASHES% >> "%LOGFILE%"
if %CRASHES% GEQ 5 goto gaveup
timeout /t 30 /nobreak >nul
goto loop

:gaveup
call "%~dp0notify-error.bat" "Backend 5 kez coktu ve durduruldu - scripts\logs\backend.log dosyasina bakin"
exit /b 1
