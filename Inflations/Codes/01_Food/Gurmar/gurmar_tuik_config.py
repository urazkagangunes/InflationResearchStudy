"""
gurmar_tuik_config.py — TUIK CPI basket weights and Gurmar category mapping.
"""

# ── TUIK 2026 TÜFE Ana Grup Ağırlıkları ────────────────────────────────────────
# Kaynak: TÜİK, 2026 (Baz yılı 2025=100)
TUIK_WEIGHTS = {
    "01": {"name": "Gıda ve alkolsüz içecekler",                               "weight": 24.44},
    "02": {"name": "Alkollü içecekler, tütün ve tütün ürünleri",               "weight": 2.75},
    "03": {"name": "Giyim ve ayakkabı",                                        "weight": 7.90},
    "04": {"name": "Konut, su, elektrik, gaz ve diğer yakıtlar",               "weight": 11.40},
    "05": {"name": "Mobilya, ev aletleri ve ev bakım hizmetleri",              "weight": 7.92},
    "06": {"name": "Sağlık",                                                   "weight": 2.79},
    "07": {"name": "Ulaştırma",                                                "weight": 16.62},
    "08": {"name": "Bilgi ve iletişim",                                        "weight": 3.10},
    "09": {"name": "Eğlence, dinlence, spor ve kültür",                        "weight": 4.34},
    "10": {"name": "Eğitim",                                                   "weight": 2.02},
    "11": {"name": "Lokantalar ve konaklama hizmetleri",                       "weight": 11.13},
    "12": {"name": "Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler", "weight": 4.49},
    "13": {"name": "Sigorta ve finansal hizmetler",                            "weight": 1.07},
}

def normalised_weights(present_codes):
    """Mevcut TUIK grupları için ağırlıkları 100 üzerinden yeniden ölçeklendirir."""
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}

# ─── Gurmar Kategori → TUIK Grup Eşleştirmesi ────────────────────────────────────
# Gürmar ana kategorilerinin TÜİK harcama gruplarına (01-12) eşleştirilmesi.

GURMAR_TO_TUIK_MAP = {
    "Meyve ve Sebze": "01",
    "Et ve Tavuk": "01",
    "Süt, Kahvaltılık, Sark.": "01",
    "Temel Gıda": "01",
    "İçecekler": "01",
    "Atıştırmalıklar": "01",
    "Bebek Ürünleri": "12",
    "Deterjan ve Temizlik": "05",
    "Kişisel Bakım": "12",
    "Ev ve Yaşam": "05",
    "Kitap, Kırtasiye": "09",
    "Petshop": "09",
}

def gurmar_category_to_tuik(category_name):
    """Gürmar kategori ismini alıp ilgili TUIK kodunu döndürür."""
    if not category_name or not isinstance(category_name, str):
        return "01"  # Varsayılan: Gıda

    return GURMAR_TO_TUIK_MAP.get(category_name.strip(), "01")
