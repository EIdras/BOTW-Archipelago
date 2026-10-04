@echo off
rem Product tests. "run-tests.cmd full" also builds whole packs (minutes): before a commit
rem that changes what a pack holds (tests/full_build.py).
cd /d "%~dp0"
set "BOTW_FULL_TESTS="
if /i "%~1"=="full" set "BOTW_FULL_TESTS=1"
"%~dp0venv\Scripts\python.exe" -m unittest discover -s tests
pause
