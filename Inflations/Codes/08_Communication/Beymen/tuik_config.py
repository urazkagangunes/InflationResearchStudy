"""
tuik_config.py — TUIK CPI basket weights and Samsung category mapping.

Provides
--------
- ``TUIK_WEIGHTS``            : 2026 CPI main-group weights (base year 2025=100)
- ``normalised_weights``      : rescale weights for a subset of present groups
- ``samsung_category_to_tuik``: map Samsung product categories to TUIK codes

TUIK Code Convention
--------------------
This file follows the **same code labels used by every other per-store
inflation calculator in this repository** (Migros, Bauhaus, Rossmann,
Vivense, …).  All downstream tooling
(``CrossStore_Compare.py``, ``inflation_engine.py``) assumes this
convention.

Samsung-Specific Mapping
------------------------
Samsung Türkiye's catalogue spans three distinct TUIK main groups, so
the weighted CPI metric actually reflects the mix of the scraped
categories (unlike e.g. Vivense where everything collapses to group 05):

    TUIK 05 (Mobilya, ev aletleri ve ev bakım hizmetleri)
      → White goods & small home appliances:
        Refrigerators, Washers & Dryers, Dishwashers,
        Air Purifier, Air Conditioners, Vacuum Cleaners,
        Cooking Appliances, Microwave Ovens

    TUIK 08 (Bilgi ve iletişim)
      → Mobile / computing / personal connected devices:
        Smartphones, Tablets, Watches, Rings,
        Mobile Accessories, Monitors, Memory & Storage

    TUIK 09 (Eğlence, dinlence, spor ve kültür)
      → Audio / video / home entertainment:
        TVs, TV Accessories, Projectors,
        Audio Sound, Audio Devices

The weighting differences between those three groups are substantial
(8→3.10, 9→4.34, 5→7.92), so the ``tuik_weighted_*`` metric is the
single most informative signal in the Samsung summary file.
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
    present in the dataset.  This is the standard treatment used by
    every per-store calculator in the repo and is required because a
    single store rarely covers all 13 TUIK groups.
    """
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}


# ─── Samsung Category → TUIK Group ───────────────────────────────────────────
# Keys exactly match the ``category`` column values written by the
# scraper (see config.TOP_LEVEL_CATEGORIES in the Samsung scripts
# package).  Keep this map in sync with that list.
_SAMSUNG_TUIK_MAP = {
    # White goods & small home appliances → 05
    "Refrigerators":       "05",
    "Washers & Dryers":    "05",
    "Dishwashers":         "05",
    "Air Purifier":        "05",
    "Air Conditioners":    "05",
    "Vacuum Cleaners":     "05",
    "Cooking Appliances":  "05",
    "Microwave Ovens":     "05",

    # Mobile / computing / personal connected devices → 08
    "Smartphones":         "08",
    "Tablets":             "08",
    "Watches":             "08",
    "Rings":               "08",
    "Mobile Accessories":  "08",
    "Monitors":            "08",
    "Memory & Storage":    "08",

    # Audio / video / home entertainment → 09
    "TVs":                 "09",
    "TV Accessories":      "09",
    "Projectors":          "09",
    "Audio Sound":         "09",
    "Audio Devices":       "09",
}


def samsung_category_to_tuik(category_name):
    """Map a Samsung product category string to a TUIK group code.

    Args
    ----
    category_name : str
        Value of the ``category`` column from a Samsung scraper CSV
        (e.g. "Smartphones", "Refrigerators", "TVs").

    Returns
    -------
    str
        TUIK group code (e.g. ``"08"``).  Falls back to ``"08"`` when
        the category is missing or unrecognised — most Samsung SKUs are
        connected electronics, so ``"Bilgi ve iletişim"`` is the safest
        default if a new category is ever introduced.
    """
    if not category_name or not isinstance(category_name, str):
        return "08"
    return _SAMSUNG_TUIK_MAP.get(category_name.strip(), "08")