"""
Configuration - all constants in one place.
"""

import os

BASE_URL = "https://www.hapeloglu.com"
PRODUCTS_PER_PAGE = 80
REQUEST_DELAY = 1.5       # seconds between requests (mean)
REQUEST_STDEV = 0.4
REQUEST_FLOOR = 0.9
DEFAULT_WORKERS = 4
MAX_RETRIES = 10
RETRY_BACKOFF = 4.0

# Resolve path relative to this file's location:
# config.py is at:  Codes/Markets/Hapeloglu/src/config.py
# Target is:        Datas/Markets/Hapeloglu/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_THIS_DIR, "..", "..", "..", "..")
OUTPUT_DIR = os.path.normpath(os.path.join(_REPO_ROOT, "Datas", "Markets", "Hapeloglu"))

# 13 main categories (depth=1 from sidebar)
CATEGORIES = {
    "Meyve, Sebze":            "/meyve-sebze",
    "Et, Tavuk, Balık":        "/et-tavuk-balik",
    "Süt, Kahvaltılık":        "/sut-kahvaltilik",
    "İçecek":                  "/icecek",
    "Temel Gıda":              "/temel-gida",
    "Fırın, Pastane":          "/firin-pastane",
    "Atıştırmalık":            "/atistirmalik",
    "Deterjan, Temizlik":      "/deterjan-temizlik",
    "Kağıt, Islak Mendil":     "/kagit-islak-mendil",
    "Kişisel Bakım, Kozmetik": "/kisisel-bakim-kozmetik",
    "Bebek":                   "/bebek",
    "Ev, Yaşam":               "/ev-yasam",
    "Evcil Hayvan":            "/evcil-hayvan",
}

# Browser-like headers
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.hapeloglu.com/",
}