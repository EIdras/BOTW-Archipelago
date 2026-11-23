@echo off
rem Breath of the Wild Archipelago from a source checkout. Players open it from the
rem Archipelago Launcher (botw.apworld). Drop a slot file (.apbotw) or a seed's zip on it, or start it.
cd /d "%~dp0"
rem pythonw: the launcher is a window, no console stays open behind it.
set "PYTHON=%~dp0venv\Scripts\pythonw.exe"
if not exist "%PYTHON%" (
    echo The checkout's Python is missing: %PYTHON%
    echo Create it first: python -m venv venv, then venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)
rem -I: no PYTHON* variable or user package of this computer reaches the tools.
start "" "%PYTHON%" -I -X utf8 "%~dp0botw_launcher\__main__.py" %*
