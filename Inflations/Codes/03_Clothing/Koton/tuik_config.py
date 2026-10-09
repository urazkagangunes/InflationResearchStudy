"""
tuik_config.py — TUIK CPI basket weights and Koton category mapping.

Provides:
  - TUIK_WEIGHTS: 2026 CPI main-group weights (base year 2025=100)
  - normalised_weights(): rescale weights for a subset of present groups
  - koton_category_to_tuik(): map Koton product categories to TUIK codes
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
    "12": {"name": "Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler",   "weight": 4.49},
    "13": {"name": "Sigorta ve finansal hizmetler",                              "weight": 1.07},
}


def normalised_weights(present_codes):
    """Return a dict {code: normalised_weight} for only the TUIK groups in *present_codes*.

    Weights are rescaled so that they sum to 100.0 among the present groups.
    """
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}


# ─── Koton Category → TUIK Group ─────────────────────────────────────────────
def koton_category_to_tuik(category_name):
    """Map a Koton product category string to a TUIK group code.

    Koton is predominantly clothing (03).  Cosmetics/perfume products are
    classified under personal care (12).
    """
    if not category_name or not isinstance(category_name, str):
        return "03"
    cat_upper = category_name.upper()
    if "COSMETICS" in cat_upper or "PERFUME" in cat_upper:
        return "12"
    return "03"
