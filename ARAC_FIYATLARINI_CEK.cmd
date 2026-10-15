@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" run_vehicle_prices.py %*
) else (
  python run_vehicle_prices.py %*
)
pause
