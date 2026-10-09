"""
tuik_config.py — TUIK CPI weights and category mapping for Golden Rose.

Golden Rose's catalogue is overwhelmingly cosmetics and personal-care items, so
all tracked top-level categories are treated as the repository's cosmetics
group.
"""

TUIK_WEIGHTS = {
    "12": {"name": "Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler", "weight": 4.4935},
}

_CATEGORY_MAP = {
    "Aksesuar": "12",
    "Cilt Bakımı": "12",
    "Dudak": "12",
    "Emily": "12",
    "Göz": "12",
    "Mini Ürünler": "12",
    "Parfüm": "12",
    "Tırnak": "12",
    "Yüz": "12",
}

_DEFAULT_CODE = "12"


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


def goldenrose_category_to_tuik(top_category, source_category=None):
    """Map Golden Rose category fields to a TUIK main-group code."""
    for value in (top_category, source_category):
        if isinstance(value, str):
            mapped = _CATEGORY_MAP.get(value.strip())
            if mapped:
                return mapped
    return _DEFAULT_CODE
