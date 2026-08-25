@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0FLASH_FIRMWARE.ps1"
echo.
pause
