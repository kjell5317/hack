@echo off
rem Project command line for Windows: .\hack help   (macOS/Linux: ./hack)
rem Makes sure uv exists, then runs scripts\hack.py with a uv-managed Python.
setlocal

rem Started from PowerShell 7 (e.g. GitHub Actions, Windows Terminal), PSModulePath
rem lists PS7's modules first and Windows PowerShell can't load them (the uv and
rem scoop installers fail on Get-ExecutionPolicy). Unset, powershell.exe rebuilds
rem its default. setlocal keeps this to this script and scripts\hack.py.
set "PSModulePath="

set "UV=uv"
where uv >nul 2>nul && goto run
set "UV=%USERPROFILE%\.local\bin\uv.exe"
if exist "%UV%" goto run

echo uv (Python + package manager) is missing, installing it...
powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 exit /b 1

:run
"%UV%" run --quiet --script "%~dp0scripts\hack.py" %*
exit /b %errorlevel%
