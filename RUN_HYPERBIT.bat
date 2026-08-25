@echo off
setlocal
cd /d "%~dp0"
title HyperBit

if not exist "config.cmd" (
    copy /y "config.example.cmd" "config.cmd" >nul
    echo.
    echo Created config.cmd.
    echo Put your Hyper API key in it, save it, then run this file again.
    start notepad.exe "%~dp0config.cmd"
    pause
    exit /b 1
)

call "%~dp0config.cmd"

if "%HYPER_API_KEY%"=="" (
    echo HYPER_API_KEY is empty in config.cmd.
    pause
    exit /b 1
)
echo %HYPER_API_KEY% | findstr /C:"REPLACE_ME" >nul
if not errorlevel 1 (
    echo Replace sk-hyper-REPLACE_ME in config.cmd with your actual Hyper key.
    pause
    exit /b 1
)

set "PYTHON_CMD="

where python3 >nul 2>nul
if not errorlevel 1 (
    python3 -c "import bleak, httpx, numpy, psutil" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python3"
)

if not defined PYTHON_CMD (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -c "import bleak, httpx, numpy, psutil" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=py -3"
    )
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import bleak, httpx, numpy, psutil" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo.
    echo HyperBit dependencies were not found in any Python installation.
    echo Installing requirements into the first Python I can find...
    echo.

    where python3 >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python3"

    if not defined PYTHON_CMD (
        where py >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=py -3"
    )

    if not defined PYTHON_CMD (
        where python >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=python"
    )

    if not defined PYTHON_CMD (
        echo Python 3 is not installed.
        pause
        exit /b 1
    )

    %PYTHON_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed.
        pause
        exit /b 1
    )
)

echo Using: %PYTHON_CMD%
echo.
%PYTHON_CMD% HyperBit.py %*
echo.
pause
