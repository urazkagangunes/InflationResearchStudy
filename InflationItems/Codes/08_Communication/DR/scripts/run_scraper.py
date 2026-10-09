"""Compatibility entry point for ``python -m scripts.run_scraper``."""

from __future__ import annotations

try:
    from .main import main
except ImportError:
    from main import main


if __name__ == "__main__":
    main()
