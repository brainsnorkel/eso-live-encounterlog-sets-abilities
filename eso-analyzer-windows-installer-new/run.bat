@echo off
REM ESO Live Encounter Log Sets & Abilities Analyzer - Windows Launcher
REM Version 0.2.3

echo ESO Live Encounter Log Sets ^& Abilities Analyzer v0.2.3
echo ========================================================
echo.

REM Check if esolog-tail executable exists
if not exist "esolog-tail.exe" (
    echo Error: esolog-tail.exe not found!
    echo Please ensure you're running this script from the installer directory.
    pause
    exit /b 1
)

echo Starting ESO Log Analyzer...
echo Usage: esolog-tail.exe --help for options
echo.

REM Run the analyzer with all passed arguments
esolog-tail.exe %*
