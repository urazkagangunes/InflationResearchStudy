"""
koctas_tuik_config.py — TUIK CPI basket weights and Koçtaş category mapping.
"""

TUIK_WEIGHTS = {
    "01": {"name": "Gıda ve alkolsüz içecekler",                               "weight": 24.44},
    "02": {"name": "Alkollü içecekler, tütün ve tütün ürünleri",                "weight": 2.75},
    "03": {"name": "Giyim ve ayakkabı",                                         "weight": 7.90},
    "04": {"name": "Konut, su, elektrik, gaz ve diğer yakıtlar",                "weight": 11.40},
    "05": {"name": "Mobilya, ev aletleri ve ev bakım hizmetleri",               "weight": 7.92},
    "06": {"name": "Sağlık",                                                    "weight": 2.79},
    "07": {"name": "Ulaştırma",                                                 "weight": 16.62},
    "08": {"name": "Bilgi ve iletişim",                                         "weight": 3.10},
    "09": {"name": "Eğlence, dinlence, spor ve kültür",                         "weight": 4.34},
    "10": {"name": "Eğitim",                                                    "weight": 2.02},
    "11": {"name": "Lokantalar ve konaklama hizmetleri",                        "weight": 11.13},
    "12": {"name": "Sigorta ve finansal hizmetler",                             "weight": 1.07},
    "13": {"name": "Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler",  "weight": 4.49},
}


def normalised_weights(present_codes):
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}


# Tüm Koçtaş kategorileri → TÜİK 05 (Mobilya, ev aletleri ve ev bakım hizmetleri)
_CATEGORY_MAP = {
    "Akülü Vidalamalar":      "05",
    "Matkaplar":              "05",
    "Kırıcılar ve Deliciler": "05",
    "Taşlamalar":             "05",
    "Testereler":             "05",
    "Zımpara ve Polisaj":     "05",
    "Boya Tabancaları":       "05",
    "Kaynak Makineleri":      "05",
    "Test ve Ölçüm":          "05",
    "Hobi Aletleri":          "05",
    "Klima":                  "09",
    "Elektrikli Isıtıcılar":  "09",
    "Hava Temizleyiciler":    "09",
    "Küçük Ev Aletleri":      "09",
    "Beyaz Eşya":             "09",
    "Aydınlatma":             "09",
    "Vantilatör":             "09",
}


def koctas_category_to_tuik(category_name):
    if not category_name or not isinstance(category_name, str):
        return "05"
    return _CATEGORY_MAP.get(category_name.strip(), "05")