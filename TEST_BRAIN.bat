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
    echo Edit config.cmd and set HYPER_API_KEY first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "pc_agent\agent.py" --home "%CD%\agent_home" --text "Say hello in one short sentence, then tell me the current time using your time tool."
pause
