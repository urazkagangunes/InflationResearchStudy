@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" collect_all.py %*
) else (
  python collect_all.py %*
)
pause
