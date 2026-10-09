"""
tuik_config.py — TUIK CPI weights and category mapping for Karaca.

Karaca is primarily a home-goods retailer, but its catalogue also contains
smaller food, personal-care, travel, and recreation slices.  This module keeps
the weighting logic local to the Karaca calculator so it can use the same
directory structure as the other newer per-store calculators.
"""

TUIK_WEIGHTS = {
    "01": {"name": "Gıda ve alkolsüz içecekler", "weight": 24.4444},
    "05": {"name": "Mobilya, ev aletleri ve ev bakım hizmetleri", "weight": 7.9201},
    "07": {"name": "Ulaştırma", "weight": 16.6169},
    "09": {"name": "Eğlence, dinlence, spor ve kültür", "weight": 4.3382},
    "12": {"name": "Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler", "weight": 4.4935},
}

_MAIN_CATEGORY_MAP = {
    "Sofra": "05",
    "Mutfak": "05",
    "Küçük Ev Aletleri": "05",
    "Ev ve Yaşam": "05",
    "Hobi Eğlence": "09",
}

_TOP_CATEGORY_OVERRIDES = {
    "Gıda": "01",
    "Kişisel Bakım": "12",
    "Kişisel Bakım ve Kozmetik": "12",
    "Pet Shop": "12",
    "Seyahat": "07",
    "Hobi Malzemeleri": "09",
    "Kırtasiye": "09",
    "Oyun ve Eğlence": "09",
    "Parti": "09",
    "Spor & Outdoor": "09",
}

_DEFAULT_CODE = "05"


def normalised_weights(present_codes):
    """Return ``{code: normalised_weight}`` for the supplied TUIK codes."""
    raw = {
        code: TUIK_WEIGHTS[code]["weight"]
        for code in present_codes
        if code in TUIK_WEIGHTS
    }
    total = sum(raw.values())
    if total == 0:
        return {}
    return {code: (weight / total) * 100.0 for code, weight in raw.items()}


def karaca_category_to_tuik(main_category, top_category):
    """Map Karaca main/top category fields to a TUIK main-group code."""
    if isinstance(top_category, str):
        mapped = _TOP_CATEGORY_OVERRIDES.get(top_category.strip())
        if mapped:
            return mapped

    if isinstance(main_category, str):
        mapped = _MAIN_CATEGORY_MAP.get(main_category.strip())
        if mapped:
            return mapped

    return _DEFAULT_CODE
