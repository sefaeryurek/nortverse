@echo off
REM Nortverse - Docker + PostgreSQL hazir mi? Degilse Docker Desktop'i baslatir ve bekler.
REM Kullanim: call "%~dp0ensure-docker.bat" "LOG_DOSYASI"   (basarisizsa errorlevel 1)

set "EDLOG=%~1"
set "DOCKER_DESKTOP=%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe"
set "ROOT=C:\Users\Sefa\Desktop\NORTVERSE - CODEX"

docker info >nul 2>&1
if not errorlevel 1 goto compose

echo [%date% %time%] Docker calismiyor, Docker Desktop baslatiliyor... >> "%EDLOG%"
if exist "%DOCKER_DESKTOP%" start "" "%DOCKER_DESKTOP%"
REM En fazla ~3 dakika bekle (36 x 5 sn)
for /l %%i in (1,1,36) do (
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1 && goto compose
)
echo [%date% %time%] HATA: Docker 3 dakikada baslamadi >> "%EDLOG%"
exit /b 1

:compose
pushd "%ROOT%"
docker compose up -d >> "%EDLOG%" 2>&1
REM Veritabani baglanti kabul edene kadar bekle (en fazla ~1 dakika)
for /l %%i in (1,1,12) do (
    docker compose exec -T db pg_isready -U nortverse -d nortverse >nul 2>&1 && (popd & exit /b 0)
    timeout /t 5 /nobreak >nul
)
popd
echo [%date% %time%] HATA: PostgreSQL hazir degil >> "%EDLOG%"
exit /b 1
