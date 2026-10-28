@echo off
REM Nortverse - Yarinin takip maclarini aksamdan analiz eder (Sprint 94 F1; Gorev Zamanlayici: 23:20).
REM Mac oncesi kararlar 48 saat icinde dondurulabilir; sabah pipeline'i uyku yuzunden gec calisirsa
REM (11:10-15:56 arasi) erken maclarin karari kacmasin diye bir gece once hazirlanir.
for /f %%I in ('powershell -NoProfile -Command "(Get-Date).AddDays(1).ToString('yyyy-MM-dd')"') do set "TOMORROW=%%I"
set "PIPELINE_ARGS=--date %TOMORROW%"
call "%~dp0run-pipeline.bat"
exit /b %errorlevel%
