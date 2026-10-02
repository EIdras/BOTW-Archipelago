@echo off
rem Breath of the Wild Archipelago. Drop a slot file (.apbotw.json) or a seed's zip on it, or start it.
cd /d "%~dp0"
set "PYTHON=%~dp0python\python.exe"
if not exist "%PYTHON%" set "PYTHON=%~dp0venv\Scripts\python.exe"
"%PYTHON%" "%~dp0tools\launcher.py" %*
pause
