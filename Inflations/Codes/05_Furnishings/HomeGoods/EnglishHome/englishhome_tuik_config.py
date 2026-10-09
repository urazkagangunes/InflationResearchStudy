"""
englishhome_tuik_config.py — English Home → TÜİK COICOP 2018 Mapping

English Home kategorilerini TÜİK 2026 TÜFE sepet kodlarına eşler.
Hocanın talimatı: Home, Home Decoration, Living kategorileri.
English Home zaten ev eşyası sitesi — Kozmetik hariç tamamı COICOP 05.

Mapping:
    05 Mobilya/ev eşyası (7.9201) ← Yatak Odası, Sofra, Mutfak, Küçük Ev Aletleri,
                                      Dekorasyon, Banyo, Halı&Kilim, Çeyiz Ürünleri,
                                      Hediye, Ev Tekstili, Bebek & Çocuk, Outlet
    13 Kişisel bakım     (4.4935) ← Kozmetik
"""

# ── TÜİK 2026 sepet ağırlıkları (COICOP 2018) ───────────────────────────────
TUIK_WEIGHTS = {
    "05": 7.9201,    # Mobilya, mefruşat ve evde kullanılan ekipmanlar
    "13": 4.4935,    # Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler
}

# ── Kategori → COICOP eşlemesi ────────────────────────────────────────────────
_CATEGORY_MAP = {
    # 05 — Ev eşyası (ana kategoriler)
    "Yatak Odası":         "05",
    "Sofra":               "05",
    "Mutfak":              "05",
    "Küçük Ev Aletleri":   "05",
    "Dekorasyon":          "05",
    "Banyo":               "05",
    "Halı&Kilim":          "05",
    "Çeyiz Ürünleri":      "05",
    "Hediye":              "05",
    "Ev Tekstili":         "05",
    "Bebek & Çocuk":       "05",
    "Outlet":              "05",

    # 13 — Kişisel bakım
    "Kozmetik":            "13",
}

_DEFAULT_CODE = "05"


def englishhome_category_to_tuik(category: str) -> str:
    """English Home kategori adını TÜİK COICOP koduna çevirir."""
    return _CATEGORY_MAP.get(category, _DEFAULT_CODE)


def normalised_weights(present_codes: list[str]) -> dict[str, float]:
    """Mevcut COICOP kodlarının ağırlıklarını 100'e normalize eder."""
    total = sum(TUIK_WEIGHTS[c] for c in present_codes if c in TUIK_WEIGHTS)
    if total == 0:
        return {}
    return {
        c: TUIK_WEIGHTS[c] / total * 100
        for c in present_codes
        if c in TUIK_WEIGHTS
    }
