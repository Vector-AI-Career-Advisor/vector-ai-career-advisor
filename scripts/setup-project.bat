@echo off
title AI Career Assistant - Environment Setup

:: Thin wrapper — all real logic lives in setup.sh (kept as the single source
:: of truth for both platforms) so the two launchers can't drift out of sync.
:: Needs Git Bash (bundled with Git for Windows: https://git-scm.com/download/win),
:: which most Windows dev machines already have since they have git.
:: Also needs Docker Desktop running, same as the .sh version.

cd /d %~dp0\..

where bash >nul 2>nul
if %errorlevel%==0 (
    bash scripts/setup.sh
    goto :eof
)

set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if exist "%GITBASH%" (
    "%GITBASH%" scripts/setup.sh
    goto :eof
)

echo.
echo ERROR: Git Bash was not found on PATH or at "%GITBASH%".
echo Install Git for Windows (it bundles Git Bash): https://git-scm.com/download/win
echo.
pause
