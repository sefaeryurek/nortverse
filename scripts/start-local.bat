@echo off
REM Nortverse - Localhost'u tek tikla baslat (masaustu kisayolu bunu calistirir).
REM Docker + veritabani -> backend (port 8000) -> frontend uretim sunucusu (port 3000) -> tarayicida bulten.
REM Gelistirme sunucusu ayri: frontend klasorunde "npm run dev" (port 3001).
REM Zaten calisan parca tekrar acilmaz.

title Nortverse baslatiliyor
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"
set "LOGFILE=%ROOT%\scripts\logs\local.log"

echo [1/4] Docker ve veritabani kontrol ediliyor...
call "%~dp0ensure-docker.bat" "%LOGFILE%"
if errorlevel 1 (
    echo HATA: Docker veya veritabani hazir degil. Docker Desktop'i acip tekrar deneyin.
    pause
    exit /b 1
)

echo [2/4] Backend kontrol ediliyor - port 8000...
netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul
if errorlevel 1 (
    REM Zamanlanmis gorevle penceresiz baslat; gorev yoksa dogrudan
    schtasks /run /tn "\Nortverse\Backend" >nul 2>&1
    if errorlevel 1 start "Nortverse Backend" /min cmd /c "%ROOT%\scripts\start-backend.bat"
) else (
    echo       Backend zaten calisiyor.
)

echo [3/4] Frontend kontrol ediliyor - port 3000...
netstat -ano | findstr /r /c:":3000 .*LISTENING" >nul
if errorlevel 1 (
    REM Uretim sunucusu denetleyiciyle, penceresiz; ilk acilista derleme birkac dakika surebilir
    schtasks /run /tn "\Nortverse\Frontend" >nul 2>&1
    if errorlevel 1 start "Nortverse Frontend" /min cmd /c "%ROOT%\scripts\frontend-supervisor.bat"
) else (
    echo       Frontend zaten calisiyor.
)

echo [4/4] Sayfa hazirlaniyor, en fazla 5 dakika bekleniyor - ilk acilista derleme yapilir...
for /l %%i in (1,1,150) do (
    powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000/giris -TimeoutSec 5 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1 && goto ready
    ping -n 3 127.0.0.1 >nul
)
echo Frontend 5 dakikada acilmadi; tarayici yine de aciliyor. Ayrinti: scripts\logs\frontend.log

:ready
start "" "http://127.0.0.1:3000/bulten"
echo Hazir. Bu pencere 5 saniye sonra kapanacak.
timeout /t 5 >nul
exit /b 0
