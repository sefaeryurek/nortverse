@echo off
REM Nortverse - Veri kaynagina ag baglantisi hazir mi? Degilse 10 sn arayla 30 kez dener (~5 dk).
REM Kullanim: call "%~dp0wait-network.bat" "LOG_DOSYASI"   (basarisizsa errorlevel 1)
REM Sebep: 21 Ekim'de PC uyanistan 40 sn sonra pipeline'i calistirdi, DNS hazir degildi, tum gun kacti.
REM Not: "timeout /t" gizli konsolda beklemez; bekleme icin ping kullanilir.

set "WNLOG=%~1"
for /l %%i in (1,1,30) do (
    powershell -NoProfile -Command "if (Test-NetConnection live5.nowgoal26.com -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1 && exit /b 0
    ping -n 11 127.0.0.1 >nul
)
echo [%date% %time%] HATA: 5 dakikada veri kaynagina baglanilamadi >> "%WNLOG%"
exit /b 1
