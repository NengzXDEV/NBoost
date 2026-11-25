@echo off
REM Nboost - build_installer.bat
REM Builds Nboost.exe (if missing) then compiles the Inno Setup installer.
REM Requires Inno Setup 6/7 installed: https://jrsoftware.org/isdl.php

setlocal

if not exist "dist\Nboost.exe" (
    echo dist\Nboost.exe not found - building it first...
    call build_exe.bat
)

set "ISCC="
for %%P in (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
    "%ProgramFiles%\Inno Setup 7\ISCC.exe"
) do (
    if exist %%P set "ISCC=%%~P"
)

if "%ISCC%"=="" (
    echo Could not find ISCC.exe. Install Inno Setup from https://jrsoftware.org/isdl.php
    echo then re-run this script, or compile installer\nboost.iss manually.
    exit /b 1
)

echo Compiling installer with "%ISCC%"...
"%ISCC%" installer\nboost.iss

echo.
echo === Done ===
echo Output: installer\Output\NboostSetup.exe
pause
