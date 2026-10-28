@echo off
REM Nortverse - Haftalik tum ligler pipeline'i (Sprint 94 F2; Gorev Zamanlayici: Pazartesi 09:30).
REM Gunluk pipeline sadece takip edilen 12 ligi isler; aday ligler icin veri bu haftalik calismada birikir.
set "PIPELINE_ARGS=--scope all"
call "%~dp0run-pipeline.bat"
exit /b %errorlevel%
