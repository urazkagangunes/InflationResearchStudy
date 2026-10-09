"""Bridge module for running the Nezih scraper through ``python -m scripts.*``."""

from __future__ import annotations

import os
import sys

_STORE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _STORE_DIR not in sys.path:
    sys.path.insert(0, _STORE_DIR)

from nezih_scraper import main


if __name__ == "__main__":
    main()
