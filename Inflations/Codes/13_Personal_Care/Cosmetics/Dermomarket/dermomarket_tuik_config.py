"""
dermomarket_tuik_config.py — Dermomarket → TÜİK COICOP 2018 Mapping

Dermomarket kategorilerini TÜİK 2026 TÜFE sepet kodlarına eşler.
COICOP 2018 kodlaması kullanılır.

Mapping:
    13 Kişisel bakım (4.4935) ← Cilt Bakımı, Güneş Bakımı, Kişisel Bakım,
                                  Makyaj, Parfüm ve Deodorant, Saç Bakımı,
                                  Ev ve Yaşam (difüzör, mum — az ürün, ayrı COICOP
                                  kodu vermek normalize ağırlığı çarpıtır)
    06 Sağlık        (2.7923) ← Ağız Bakımı, Anne Bebek, Vitamin ve Sağlık
"""

# ── TÜİK 2026 sepet ağırlıkları (COICOP 2018, ilgili kodlar) ─────────────────
TUIK_WEIGHTS = {
    "06": 2.7923,    # Sağlık
    "13": 4.4935,    # Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler
}

# ── Kategori → COICOP eşlemesi ────────────────────────────────────────────────
_CATEGORY_MAP = {
    # 13 — Kişisel bakım
    "Cilt Bakımı":           "13",
    "Güneş Bakımı":          "13",
    "Kişisel Bakım":         "13",
    "Makyaj":                "13",
    "Parfüm ve Deodorant":   "13",
    "Saç Bakımı":            "13",
    "Ev ve Yaşam":           "13",

    # 06 — Sağlık
    "Ağız Bakımı":           "06",
    "Anne Bebek":            "06",
    "Vitamin ve Sağlık":     "06",
}

# Varsayılan: bilinmeyen kategori → 13 (Kişisel bakım)
_DEFAULT_CODE = "13"


def dermomarket_category_to_tuik(category: str) -> str:
    """Dermomarket kategori adını TÜİK COICOP koduna çevirir."""
    return _CATEGORY_MAP.get(category, _DEFAULT_CODE)


def normalised_weights(present_codes: list[str]) -> dict[str, float]:
    """
    Mevcut COICOP kodlarının ağırlıklarını 100'e normalize eder.

    Örnek: sadece 12 ve 06 varsa →
        12: 4.49 / (4.49 + 2.79) * 100 = 61.68
        06: 2.79 / (4.49 + 2.79) * 100 = 38.32
    """
    total = sum(TUIK_WEIGHTS[c] for c in present_codes if c in TUIK_WEIGHTS)
    if total == 0:
        return {}
    return {
        c: TUIK_WEIGHTS[c] / total * 100
        for c in present_codes
        if c in TUIK_WEIGHTS
    }