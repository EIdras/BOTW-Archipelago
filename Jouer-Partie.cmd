@echo off
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" "%~dp0tools\play_session.py" %*
pause
