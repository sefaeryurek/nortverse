@echo off
REM Nortverse'i Tailscale agindaki arkadasla paylasir (https://<bilgisayar-adi>.<ag-adi>.ts.net).
REM Site bu bilgisayarda acik olmali (Nortverse Baslat). Paylasimi kapatmak icin: paylasim-kapat.bat
where tailscale >nul 2>&1
if errorlevel 1 (
    echo Tailscale kurulu degil. Once https://tailscale.com/download adresinden kurup giris yapin.
    pause
    exit /b 1
)
tailscale serve --bg 3000
echo.
tailscale serve status
echo.
echo Yukaridaki https adresini arkadasiniza verin. Giris icin kendi kullanici adi ve sifresi gerekir.
pause
