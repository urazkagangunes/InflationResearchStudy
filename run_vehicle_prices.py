"""Portable entry point; execute from the repository root or any directory."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'InflationItems/Codes/07_Transport/VehiclePrices'))
from run_prices import main

if __name__ == '__main__':
    raise SystemExit(main())
