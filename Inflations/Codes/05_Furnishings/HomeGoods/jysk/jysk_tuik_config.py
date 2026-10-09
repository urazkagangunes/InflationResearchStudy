"""
jysk_tuik_config.py - TUIK weights for the JYSK calculator

The daily CSVs carry no category column, so every product maps to COICOP 05,
the same way the English Home calculator handles its two-column files.
"""

# TUIK 2026 CPI basket weight (COICOP 2018), as in englishhome_tuik_config.py
TUIK_WEIGHTS = {
    "05": 7.9201,  # Furnishings, household equipment and routine maintenance
}


def normalised_weights(present_codes: list[str]) -> dict[str, float]:
    """Rescale the weights of the present COICOP codes so they sum to 100."""
    total = sum(TUIK_WEIGHTS[c] for c in present_codes if c in TUIK_WEIGHTS)
    if total == 0:
        return {}
    return {
        c: TUIK_WEIGHTS[c] / total * 100
        for c in present_codes
        if c in TUIK_WEIGHTS
    }
