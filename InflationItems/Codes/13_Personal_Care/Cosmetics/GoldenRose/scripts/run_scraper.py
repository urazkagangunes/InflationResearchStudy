"""Compatibility entry point for `python -m scripts.run_scraper`."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main


if __name__ == "__main__":
    main()
