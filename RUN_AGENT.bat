@echo off
setlocal
cd /d "%~dp0"

if exist "config.cmd" call "config.cmd"

if not exist ".venv\Scripts\python.exe" (
    echo Run SETUP_PC.bat first.
    pause
    exit /b 1
)

if "%HYPER_API_KEY%"=="" (
    echo HYPER_API_KEY is not set.
    echo Edit config.cmd first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "pc_agent\agent.py" --home "%CD%\agent_home" %*
pause
