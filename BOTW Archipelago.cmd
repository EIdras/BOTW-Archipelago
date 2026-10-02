@echo off
rem Breath of the Wild Archipelago. Drop a slot file (.apbotw.json) or a seed's zip on it, or start it.
cd /d "%~dp0"
set "PYTHON=%~dp0python\python.exe"
if not exist "%PYTHON%" set "PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo Python is missing next to this file: %~dp0python\python.exe
    echo Unzip the whole release first ^(right-click the zip, Extract All^), then start
    echo BOTW Archipelago.cmd from the unzipped folder, not from inside the zip.
    pause
    exit /b 1
)
rem -I: no PYTHON* variable or user package of this computer reaches the tools.
"%PYTHON%" -I "%~dp0tools\launcher.py" %*
pause
