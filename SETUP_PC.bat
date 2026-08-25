@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo HyperBit - Windows PC setup
echo ==========================================

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    where python3 >nul 2>nul
    if %errorlevel%==0 (
        set "PY=python3"
    ) else (
        where python >nul 2>nul
        if %errorlevel%==0 (
            set "PY=python"
        ) else (
            echo Python 3 was not found.
            echo Install Python 3, then run this again.
            pause
            exit /b 1
        )
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
)

echo Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo Installing HyperBit PC dependencies...
".venv\Scripts\python.exe" -m pip install -r "pc_agent\requirements.txt"
if errorlevel 1 goto :fail

if not exist "config.cmd" (
    copy /y "config.example.cmd" "config.cmd" >nul
    echo.
    echo Created config.cmd.
    echo EDIT config.cmd and put your Hyper API key in it before running the agent.
)

echo.
echo Setup complete.
echo Next:
echo   1. Edit config.cmd
echo   2. Run TEST_BRAIN.bat
echo   3. Build/flash firmware with BUILD_FIRMWARE.bat
echo   4. Run RUN_AGENT.bat
pause
exit /b 0

:fail
echo.
echo Setup failed. See the error above.
pause
exit /b 1
