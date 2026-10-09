"""
stradivarius_tuik_config.py — TUIK CPI basket weights and Stradivarius category mapping.

Stradivarius kategorileri iki TUIK koduna map edilir:
  "03" — Giyim ve ayakkabı  (weight: 7.90)
  "13" — Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler  (weight: 4.49)
        (Çanta, bijuteri, aksesuar bu koda girer)

Bu ayrım olmadan tüm ürünler tek koda düşer ve
tuik_weighted == avg_inflation olur — weighting işlevsiz hale gelir.
"""

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
    "12": {"name": "Sigorta ve finansal hizmetler",                              "weight": 1.07},
    "13": {"name": "Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler",   "weight": 4.49},
}


def normalised_weights(present_codes):
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}


# "03" — Giyim ve ayakkabı
_CAT_03 = {
    "Tişört", "Jean", "Etek", "Elbise", "Pantolon",
    "Hırka ve ceket", "Trençkot ve kaban", "Sweatshirt",
    "Gömlek ve Bluz", "Triko", "Top ve body", "Ceket",
    "Bikini ve Mayo", "Şort ve Bermuda",
    "Topuklu ayakkabı", "Sandalet", "Çizme - Bot", "Spor ayakkabı",
    # Editoryal kategoriler giyim ağırlıklı olduğu için 03'e atanır
    "Yeni koleksiyon", "Yeni", "Ürüne göre alışveriş", "Ürüne göre satın al",
}

# "13" — Çeşitli mal ve hizmetler (çanta, bijuteri, aksesuar)
_CAT_13 = {
    "Çanta", "Bijuteri", "Aksesuar", "Cüzdan",
}


def stradivarius_category_to_tuik(category_name: str) -> str:
    """
    Stradivarius kategori adını TUIK CPI koduna çevirir.

    Önce tam eşleşme dener, sonra " > " ile parent'a bakar.
    Eşleşme bulunamazsa varsayılan olarak "03" döner.
    """
    if not category_name or not isinstance(category_name, str):
        return "03"

    cat = category_name.strip()

    # Tam eşleşme
    if cat in _CAT_03:
        return "03"
    if cat in _CAT_13:
        return "13"

    # Parent eşleşmesi: "Jean > D91 Düşük Bel" → "Jean" → "03"
    if " > " in cat:
        parent = cat.split(" > ")[0].strip()
        if parent in _CAT_03:
            return "03"
        if parent in _CAT_13:
            return "13"

    return "03"