"""
tuik_config.py — TUIK CPI basket weights and Vivense category mapping.

Provides:
  - TUIK_WEIGHTS:                2026 CPI main-group weights (base year 2025=100)
  - normalised_weights:           rescale weights for a subset of present groups
  - vivense_category_to_tuik:     map Vivense product categories to TUIK codes

TUIK Code Convention
--------------------
This file follows the **same code labels used by every other per-store
inflation calculator in this repository** (Migros, Bauhaus, Rossmann, …).
All downstream tooling (``CrossStore_Compare.py``, ``inflation_engine.py``)
assumes this convention.

Vivense-Specific Mapping
------------------------
Vivense is an online furniture / home-goods retailer.  Almost every
product falls under TUIK group "05" (Mobilya, ev aletleri ve ev bakım
hizmetleri).  The remaining items split across two adjacent groups:

    Mobilya / Aydınlatma / Halı / Ev Tekstili /
    Ev Dekorasyonu / Banyo / Antre / Sofra / Yapı Market /
    Yatak Odası / Oturma Odası / Yemek Odası / Çalışma Odası /
    Bahçe Mobilyaları / Uyku Grubu / Bebek-Çocuk-Genç Odası → 05

Because the Vivense catalogue is overwhelmingly furniture and home
furnishings, the ``tuik_weighted_*`` metric will be very close to the
simple ``avg_inflation_*`` metric in practice — but it is still kept
so that the output schema stays compatible with the other store
calculators.
"""

# ── TUIK 2026 TÜFE Main-Group Weights ────────────────────────────────────────
# Source: TÜİK, published 2026-03-03, base year 2025=100.
# Code labelling matches the rest of this repository's per-store calculators.
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
    """Return ``{code: normalised_weight}`` for the TUIK groups in *present_codes*.

    Weights are rescaled so they sum to 100.0 among the groups actually
    present in the dataset.  This is the standard treatment used by every
    per-store calculator in the repo and is required because a single
    store rarely covers all 13 TUIK groups.
    """
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}


# ─── Vivense Category → TUIK Group ───────────────────────────────────────────
# Vivense's top-level navigation categories (as written by the scraper to
# the ``category`` column).  Every entry in the curated list maps to TUIK
# group "05" — household furniture & furnishings — which is the dominant
# expenditure class for an online furniture retailer.
_VIVENSE_TUIK_MAP = {
    "Oturma Odası":                   "05",
    "Yatak Odası":                    "05",
    "Yemek Odası ve Mutfak":          "05",
    "Bebek, Çocuk ve Genç Odası":     "05",
    "Çalışma Odası":                  "05",
    "Bahçe Mobilyaları":              "05",
    "Aydınlatma":                     "05",
    "Halı":                           "05",
    "Ev Tekstili":                    "05",
    "Ev Dekorasyonu":                 "05",
    "Banyo":                          "05",
    "Antre Dekorasyonu":              "05",
    "Sofra":                          "05",
    "Uyku Grubu":                     "05",
    "Yapı Market":                    "05",
}


def vivense_category_to_tuik(category_name):
    """Map a Vivense product category string to a TUIK group code.

    Args
    ----
    category_name : str
        Value of the ``category`` column from a Vivense scraper CSV
        (e.g. "Oturma Odası", "Aydınlatma").

    Returns
    -------
    str
        TUIK group code (e.g. ``"05"``).  Defaults to ``"05"`` when the
        category is missing or unrecognised, which is the statistically
        correct fallback for a furniture / home-goods catalogue.
    """
    if not category_name or not isinstance(category_name, str):
        return "05"
    return _VIVENSE_TUIK_MAP.get(category_name.strip(), "05")