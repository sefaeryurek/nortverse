@echo off
REM Nortverse - Frontend uretim derlemesi (kod degistikten sonra calistirin).
REM Bostaki yuvaya derler; basarisizsa calisan site etkilenmez. Basariliysa site en gec 15 sn icinde
REM yeni surume gecer. Ayrinti: scripts\logs\frontend-build.log
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0frontend-build.ps1"
set "CODE=%errorlevel%"
if "%~1"=="" pause
exit /b %CODE%
