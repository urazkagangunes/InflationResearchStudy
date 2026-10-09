"""
tuik_config.py — TUIK CPI basket weights and Rossmann category mapping.

Provides:
  - TUIK_WEIGHTS:        2026 CPI main-group weights (base year 2025=100)
  - normalised_weights:  rescale weights for a subset of present groups
  - rossmann_category_to_tuik: map Rossmann product categories to TUIK codes

TUIK Code Convention
--------------------
This file follows the **same code labels used by every other per-store
inflation calculator in this repository** (Migros, Bauhaus, …).  Under
this convention:

    Code "12"  →  Kişisel bakım, sosyal koruma ve çeşitli mal ve
                   hizmetler                          weight 4.49%
    Code "13"  →  Sigorta ve finansal hizmetler       weight 1.07%

The numerical weights themselves match the TÜİK 2026 publication
(2025=100 base).  Only the code labels differ from the very latest
COICOP-2018 ordering — but since all per-store calculators agree on the
labelling, downstream tools (``CrossStore_Compare.py``,
``inflation_engine.py``) can compare Rossmann outputs against Migros /
Bauhaus / etc. without any translation step.

Cosmetics-Specific Mapping
--------------------------
Rossmann is a drug-store / cosmetics retailer.  Almost every product
falls under TUIK group "12" (Personal care).  The remaining items split
across the household-cleaning and health groups::

    Makyaj          → 12  (Kişisel bakım)
    Cilt Bakımı     → 12
    Kişisel Bakım   → 12
    Anne & Bebek    → 12  (mostly baby hygiene / personal-care goods)
    Sağlık & Gıda   → 06  (Sağlık)        — vitamins / supplements
    Temizlik        → 05  (Mobilya/ev)    — household cleaning supplies
    Ev & Yaşam      → 05  (Mobilya/ev)

Because almost all products land in a single TUIK group, the
``tuik_weighted_*`` metric is, in practice, very close to the simple
``avg_inflation_*`` metric for Rossmann — but it is still kept so that
the output schema stays compatible with the other store calculators.
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


# ─── Rossmann Category → TUIK Group ──────────────────────────────────────────
# Rossmann's product taxonomy has 7 top-level navigation categories.  The
# scraper writes the navigation category name to the ``category`` column,
# so a flat dict mapping is sufficient.
_ROSSMANN_TUIK_MAP = {
    "Makyaj":         "12",   # Make-up                  → Personal care
    "Cilt Bakımı":    "12",   # Skin care                → Personal care
    "Kişisel Bakım":  "12",   # Personal care            → Personal care
    "Anne & Bebek":   "12",   # Mother & baby (mostly hygiene & toiletries)
    "Sağlık & Gıda":  "06",   # Health & food (vitamins, supplements dominant)
    "Temizlik":       "05",   # Cleaning supplies        → Household maintenance
    "Ev & Yaşam":     "05",   # Home & lifestyle         → Furnishings
}


def rossmann_category_to_tuik(category_name):
    """Map a Rossmann navigation category to a TUIK 2-digit group code.

    Args
    ----
    category_name : str
        Value of the ``category`` column from a Rossmann scraper CSV
        (e.g. "Makyaj", "Sağlık & Gıda").

    Returns
    -------
    str
        TUIK group code (e.g. ``"12"``).  Defaults to ``"12"`` (Personal
        care) when the category is missing or unrecognised, which is the
        statistically-correct fallback for a drug-store catalogue.
    """
    if not category_name or not isinstance(category_name, str):
        return "12"
    return _ROSSMANN_TUIK_MAP.get(category_name.strip(), "12")