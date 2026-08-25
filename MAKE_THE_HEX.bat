@echo off
setlocal
cd /d "%~dp0"
title HyperBit - Make the HEX

echo.
echo ============================================
echo   HyperBit - MAKE THE HEX FOR ME
echo ============================================
echo.
echo You do NOT need to type commands.
echo This will set up the PC tools and compile:
echo.
echo   firmware\HyperBit.hex
echo.
echo Internet is required the first time.
echo.
pause

call "%~dp0SETUP_PC.bat"
if errorlevel 1 goto :fail

call "%~dp0BUILD_FIRMWARE.bat"
if errorlevel 1 goto :fail

echo.
echo ============================================
echo DONE
echo ============================================
echo.
echo Your compiled firmware is:
echo   firmware\HyperBit.hex
echo.
echo Plug the micro:bit V2 into USB and run:
echo   FLASH_FIRMWARE.bat
echo.
pause
exit /b 0

:fail
echo.
echo Something failed.
echo Screenshot/copy the LAST error lines and send them to ChatGPT.
echo You are not expected to debug this yourself.
echo.
pause
exit /b 1
