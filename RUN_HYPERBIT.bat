@echo off
setlocal
cd /d "%~dp0"
title HyperBit

set "BLE_TEST="
if /I "%~1"=="--ble-test" set "BLE_TEST=1"

if not defined BLE_TEST (
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
)

set "PYTHON_CMD="
set "IMPORT_CHECK=import bleak, httpx, numpy, psutil, faster_whisper; import importlib.metadata as m; assert tuple(map(int,m.version('bleak').split('.')[:3])) >= (2,1,1)"
if defined BLE_TEST set "IMPORT_CHECK=import bleak; import importlib.metadata as m; assert tuple(map(int,m.version('bleak').split('.')[:3])) >= (2,1,1)"

where python3 >nul 2>nul
if not errorlevel 1 (
    python3 -c "%IMPORT_CHECK%" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python3"
)

if not defined PYTHON_CMD (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -c "%IMPORT_CHECK%" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=py -3"
    )
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "%IMPORT_CHECK%" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo.
    echo HyperBit dependencies are missing or the installed Bleak is too old.
    echo Installing/upgrading requirements into the first Python I can find...
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

    %PYTHON_CMD% -m pip install --upgrade -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed.
        pause
        exit /b 1
    )
)

echo Using: %PYTHON_CMD%
if defined BLE_TEST echo Mode: BLE transport / firmware diagnostic only
echo.
%PYTHON_CMD% HyperBit.py %*
echo.
pause
