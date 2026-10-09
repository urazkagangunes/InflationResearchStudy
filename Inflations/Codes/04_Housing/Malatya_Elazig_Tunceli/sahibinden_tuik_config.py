"""
sahibinden_tuik_config.py — TUIK CPI basket weights and Sahibinden city mapping.

Provides:
  - TUIK_WEIGHTS: 2026 CPI main-group weights (base year 2025=100)
  - normalised_weights(): rescale weights for a subset of present groups
  - sahibinden_city_to_tuik(): map Sahibinden city keys to TUIK codes
"""

# ── TUIK 2026 TÜFE Main-Group Weights ────────────────────────────────────────
# Source: TÜİK, published 2026-03-03, base year 2025=100
TUIK_WEIGHTS = {
    "01": {"name": "Gıda ve alkolsüz içecekler",                                "weight": 24.44},
    "02": {"name": "Alkollü içecekler, tütün ve tütün ürünleri",                 "weight": 2.75},
    "03": {"name": "Giyim ve ayakkabı",                                          "weight": 7.90},
    "04": {"name": "Konut, su, elektrik, gaz ve diğer yakıtlar",                 "weight": 11.40},
    "05": {"name": "Mobilya, ev aletleri ve ev bakım hizmetleri",                "weight": 7.92},
    "06": {"name": "Sağlık",                                                     "weight": 2.79},
    "07": {"name": "Ulaştırma",                                                  "weight": 16.62},
    "08": {"name": "Bilgi ve iletişim",                                          "weight": 3.10},
    "09": {"name": "Eğlence, dinlence, spor ve kültür",                          "weight": 4.34},
    "10": {"name": "Eğitim",                                                     "weight": 2.02},
    "11": {"name": "Lokantalar ve konaklama hizmetleri",                         "weight": 11.13},
    "12": {"name": "Sigorta ve finansal hizmetler",                              "weight": 1.07},
    "13": {"name": "Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler",   "weight": 4.49},
}


def normalised_weights(present_codes):
    """Return {code: normalised_weight} for only the TUIK groups in present_codes.

    Weights are rescaled so they sum to 100.0 among the present groups.
    """
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}


# ── Sahibinden City → TUIK Group ─────────────────────────────────────────────
# Tüm kiralık daire ilanları → TUIK 04 (Konut, su, elektrik, gaz ve diğer yakıtlar)

_CITY_MAP = {
    "malatya": "04",
    "elazig":  "04",
    "tunceli": "04",
}


def sahibinden_city_to_tuik(city_key):
    """Map a Sahibinden city key to a TUIK group code."""
    if not city_key or not isinstance(city_key, str):
        return "04"
    return _CITY_MAP.get(city_key.strip().lower(), "04")
