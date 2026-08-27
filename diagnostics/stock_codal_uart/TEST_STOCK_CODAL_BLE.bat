@echo off
setlocal
cd /d "%~dp0"

set "PY=python"
where py >nul 2>&1 && set "PY=py -3"

echo Using: %PY%
%PY% -m pip install --upgrade "bleak>=3.0.2"
if errorlevel 1 goto :fail

%PY% TEST_STOCK_CODAL_BLE.py %*
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Diagnostic completed successfully.
) else (
  echo Diagnostic exit code: %RC%
)
pause
exit /b %RC%

:fail
echo Failed to install/update Bleak.
pause
exit /b 1
