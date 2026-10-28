@echo off
REM Nortverse'i Tailscale agindaki arkadasla paylasir (https://<bilgisayar-adi>.<ag-adi>.ts.net).
REM Paylasilan, uretim sunucusudur (127.0.0.1:3000, frontend-supervisor). Gelistirme sunucusu (3001) paylasilmaz.
REM Paylasimi kapatmak icin: paylasim-kapat.bat
where tailscale >nul 2>&1
if errorlevel 1 (
    echo Tailscale kurulu degil. Once https://tailscale.com/download adresinden kurup giris yapin.
    pause
    exit /b 1
)
REM Uretim sunucusu acik degilse baslat (gorev yoksa denetleyiciyi dogrudan)
netstat -ano | findstr /r /c:":3000 .*LISTENING" >nul
if errorlevel 1 (
    schtasks /run /tn "\Nortverse\Frontend" >nul 2>&1
    if errorlevel 1 start "Nortverse Frontend" /min cmd /c "%~dp0frontend-supervisor.bat"
    echo Frontend baslatiliyor - ilk acilista derleme birkac dakika surebilir.
)
tailscale serve --bg 3000
echo.
tailscale serve status
echo.
echo Yukaridaki https adresini arkadasiniza verin. Giris icin kendi kullanici adi ve sifresi gerekir.
pause
