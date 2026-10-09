"""
Configuration for Happy Center scraper.
All settings, URLs, category definitions.
"""

import os

# --- URLs ---
BASE_URL = "https://www.happycenter.com.tr"

# --- Request settings ---
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

MAX_RETRIES = 3
REQUEST_DELAY = 1.5  # seconds between requests (polite scraping)
MAX_PAGES = 200      # safety cap per subcategory

# --- Categories ---
# Top-level > Subcategory mapping
# Keys = display name for CSV, Values = URL path (relative to BASE_URL)
CATEGORIES = {
    # Kuru Gıda
    "Çay - Şeker - Bakliyat - Un - Makarna": "/Kuru_Gıda/Çay_-_Şeker_-_Bakliyat_-_Un_-_Makarna",
    "İçecek Grubu": "/Kuru_Gıda/İçecek_Grubu",
    "Çorba - Sıvı Yağlar - Margarin": "/Kuru_Gıda/Çorba_-_Sıvı_Yağlar_-_Margarin",
    "Konserve - Soslar - Unlu Mamüller": "/Kuru_Gıda/Konserve_-_Soslar_-_Unlu_Mamüller",
    "Atıştırmalık": "/Kuru_Gıda/Atıştırmalık",

    # Taze Ürünler
    "Yoğurt - Dondurma": "/Taze_Ürünler/Yoğurt_-_Dondurma",
    "Sütlük Grubu": "/Taze_Ürünler/Sütlük_Grubu",
    "Manav": "/Taze_Ürünler/Manav",
    "Kahvaltılık": "/Taze_Ürünler/Kahvaltılık",
    "Kasap - Şarküter - Açık Bakliyat": "/Taze_Ürünler/Kasap_-_Şarküter_-_Açık_Bakliyat",

    # Gıda Dışı
    "Temizlik Yardımcıları": "/Gıda_Dışı/Temizlik_Yardımcıları",
    "Tekstil - Kitap - Pet - Oyuncak": "/Gıda_Dışı/Tekstil_-_Kitap_-_Pet_-_Oyuncak",
    "Temizlik": "/Gıda_Dışı/Temizlik",
    "Kozmetik": "/Gıda_Dışı/Kozmetik",
    "Hijyen Bezleri - Bebe Ürünleri": "/Gıda_Dışı/Hijyen_Bezleri_-_Bebe_Ürünleri",
}

# --- Output ---
# Path: src/config.py -> src -> HappyCenter -> Markets -> Codes -> InflationResearchStudy
#       1                2        3              4         5
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))),
    "Datas", "Markets", "HappyCenter"
)