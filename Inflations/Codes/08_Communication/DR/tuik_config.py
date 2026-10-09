"""
tuik_config.py — TUIK weights and D&R category mapping.

D&R's technology catalogue spans several CPI main groups, so the
store-level weighted inflation metric needs a category map instead of a
single fallback code.
"""

TUIK_WEIGHTS = {
    "01": {"name": "Gıda ve alkolsüz içecekler", "weight": 24.44},
    "02": {"name": "Alkollü içecekler, tütün ve tütün ürünleri", "weight": 2.75},
    "03": {"name": "Giyim ve ayakkabı", "weight": 7.90},
    "04": {"name": "Konut, su, elektrik, gaz ve diğer yakıtlar", "weight": 11.40},
    "05": {"name": "Mobilya, ev aletleri ve ev bakım hizmetleri", "weight": 7.92},
    "06": {"name": "Sağlık", "weight": 2.79},
    "07": {"name": "Ulaştırma", "weight": 16.62},
    "08": {"name": "Bilgi ve iletişim", "weight": 3.10},
    "09": {"name": "Eğlence, dinlence, spor ve kültür", "weight": 4.34},
    "10": {"name": "Eğitim", "weight": 2.02},
    "11": {"name": "Lokantalar ve konaklama hizmetleri", "weight": 11.13},
    "12": {
        "name": "Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler",
        "weight": 4.49,
    },
    "13": {"name": "Sigorta ve finansal hizmetler", "weight": 1.07},
}


def normalised_weights(present_codes):
    """Return category weights re-scaled to sum to 100 for present codes."""
    raw = {
        code: TUIK_WEIGHTS[code]["weight"]
        for code in present_codes
        if code in TUIK_WEIGHTS
    }
    total = sum(raw.values())
    if total == 0:
        return {}
    return {code: (weight / total) * 100.0 for code, weight in raw.items()}


_CATEGORY_DEFAULTS = {
    "Elektronik Diğer": "08",
    "Ev Elektroniği": "09",
    "Foto & Kamera": "09",
    "Giyilebilir Teknoloji": "08",
    "Isıtma ve Soğutma": "05",
    "Kişisel Bakım & Sağlık": "12",
    "Kobo E-kitap Okuyucular": "08",
    "Küçük Ev Aletleri": "05",
    "Masaüstü Gereçleri": "08",
    "Ofis Teknolojileri": "08",
    "Outdoor": "07",
    "Oyun & Konsol": "09",
    "Tablet & PC Aksesuarları": "08",
    "Telefon": "08",
    "Telefon Aksesuarları": "08",
}

_SUBCATEGORY_OVERRIDES = {
    "Akıllı Ev Sistemleri": "05",
    "Aydınlatma Ve Prizler": "05",
    "Elektrikli Scooter": "07",
    "Erkek Tıraş Ürünleri": "12",
    "Isıtma": "05",
    "Masaj Aletleri": "12",
    "Oyuncu Koltukları": "05",
    "Sağlık Ürünleri": "12",
}


def _clean(value):
    return " ".join(str(value or "").split())


def dr_category_to_tuik(category_name, subcategory_name=None, source_category=None):
    """Map D&R product categories to a TUIK main-group code."""
    category = _clean(category_name)
    subcategory = _clean(subcategory_name)
    source = _clean(source_category)

    if subcategory in _SUBCATEGORY_OVERRIDES:
        return _SUBCATEGORY_OVERRIDES[subcategory]

    if "Outdoor" in source:
        return "07"

    if category in _CATEGORY_DEFAULTS:
        return _CATEGORY_DEFAULTS[category]

    return "08"
