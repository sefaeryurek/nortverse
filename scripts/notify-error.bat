@echo off
REM Nortverse - Gorev hatasini ekranda gosterir ve masaustune not birakir.
REM Kullanim: call "%~dp0notify-error.bat" "Mesaj"
REM Not: mesajda parantez kullanmayin - cagiran if/else blogunu erken kapatabilir.

set "NV_MSG=%~1"
set "NV_NOTE=%USERPROFILE%\Desktop\NORTVERSE-HATA.txt"
echo [%date% %time%] %NV_MSG% >> "%NV_NOTE%"
REM 12 saat ekranda kalir; oturum kilitliyse acilinca gorunur
msg "%USERNAME%" /TIME:43200 "Nortverse uyari: %NV_MSG% - ayrinti: Masaustu\NORTVERSE-HATA.txt" >nul 2>&1
exit /b 0
