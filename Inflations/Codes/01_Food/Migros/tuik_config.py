"""
tuik_config.py — TUIK CPI basket weights and Migros category mapping.

Provides:
  - TUIK_WEIGHTS: 2026 CPI main-group weights (base year 2025=100)
  - normalised_weights(): rescale weights for a subset of present groups
  - migros_category_to_tuik(): map Migros product categories to TUIK codes
"""

# ── TUIK 2026 TÜFE Main-Group Weights ────────────────────────────────────────
# Source: TÜİK, published 2026-03-03, base year 2025=100
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
    """Return a dict {code: normalised_weight} for only the TUIK groups in *present_codes*.

    Weights are rescaled so that they sum to 100.0 among the present groups.
    """
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}


# ─── Migros Category → TUIK Group ────────────────────────────────────────────
# Migros has ~700 fine-grained category names.  We classify them via keyword
# look-ups; anything that doesn't match falls into group 01 (food), which is
# the dominant product type.

_TUIK_12_KEYWORDS = [
    # Personal care & hygiene
    "Şampuan", "Krem", "Deodorant", "Parfüm", "Makyaj", "Tıraş", "Diş",
    "Ağız Bakım", "Ağda", "Saç ", "Oje", "Güzellik", "Nemlendirici",
    "Vücut", "Kolonya", "Güneş Kremi", "Güneş Yağı", "Güneşsiz",
    "Güneş Sonrası", "Fondöten", "Kapatıcı", "Maskara", "Ruj", "Göz Farı",
    "Eyeliner", "Kaş Makyaj", "Manikür", "Pedikür", "Saç Boyama",
    "Saç Renk", "Saç Fırça", "Saç Düzleştirici", "Saç Kurutma",
    "Saç Jöle", "Saç Köpüğü", "Saç Onarıcı", "Saç Spreyi", "Kuru Şampuan",
    "Tüy Dökücü", "Tüy Sarartıcı", "Takma Tırnak", "Pişik Kremi",
    "Yara Bandı", "Pamuk", "Kulak Çubuğu", "Islak Mendil",
    "Ped", "Tampon", "Günlük Ped", "Ultra Ped", "Prezervatif",
    "Kayganlaştırıcı", "Vazelin", "Bebek Kremi", "Wax",
    "Kişisel Bakım", "Vücut Losyon", "Vücut Spreyi", "Yüz Maskesi",
    "Yüz Serumu", "Yüz Temizleme", "Yüz Toniği", "Lif, Sünger",
    "Sıvı Sabun", "Organik Ağız Bakım", "Organik Saç Bakım",
    "Makyaj Temizleme", "Makyaj Fırçası", "Makyaj Aynası", "Makyaj Çantası",
    "Renkli Saç Boya", "Yarı Set Boya", "Set Boya", "Tıraş Bıçağı",
    "Tıraş Jeli", "Tıraş Kolonyası", "Tıraş Köpüğü", "Tıraş Losyonu",
    "Tıraş Makin", "Tıraş Sabunu", "Kullan At Tıraş",
    "Kadın Tıraş", "Kadın Deodorant", "Kadın Parfüm",
    "Saç, Sakal", "Masaj Aleti", "Tüy Toplayıcı",
    "Göğüs Koruyucu", "Gül Suyu",
]

_TUIK_05_KEYWORDS = [
    # Furniture, household appliances, home maintenance
    "Temizlik", "Deterjan", "Çamaşır", "Bulaşık", "Tencere", "Tava",
    "Bıçak", "Süpürge", "Ütü", "Kurutma Makinesi", "Çamaşır Makinesi",
    "Sahan", "Fırın Kabı", "Fırın Tepsisi", "Kek Kalıbı", "Tepsi",
    "Mutfak Bıçağı", "Mutfak El Alet", "Mutfak Ekipman", "Mutfak Sarf",
    "Mutfak Tekstil", "Mutfak ve Banyo", "Saklama Kabı",
    "Süzgeç", "Rende", "Kesme Tahtası", "Nihale", "Tirbüşon",
    "Pişirme Kağıdı", "Streç Film", "Çöp Poşeti", "Mandal",
    "Çamaşır İpi", "Çamaşır Kurutma", "Çamaşır Koku",
    "Çamaşır ve Kirli", "Hurç", "Yer Bezi", "Mop", "Paspas",
    "Temizlik Bez", "Temizlik Fırça", "Temizlik Havlu", "Temizlik Seti",
    "Mikrofiber", "Halı Şampuan", "Kireç Sök", "Kireç Önleyici",
    "Yağ Çözücü", "Lavabo Açıcı", "Lavabo Pompası", "Leke Çıkarıcı",
    "Tül Beyazlatıcı", "Renk Koruyucu Mendil", "Likid Temizleyici",
    "Sıvı Yüzey Temizleyici", "Rezervuar Blok", "Tuvalet Kokusu",
    "Oda Kokusu", "Kokulu Mum", "Parlatıcı", "Çamaşır Makinesi Tablet",
    "Klasik Çamaşır Suyu", "Jel Çamaşır Suyu", "Jel Bulaşık",
    "Sıvı Bulaşık", "Sıvı Çamaşır", "Toz Deterjan",
    "Konsantre Çamaşır", "Klasik Çamaşır Yum",
    # Home textiles & furnishing
    "Yastık", "Yatak", "Yorgan", "Pike", "Çarşaf", "Perde",
    "Havlu", "Sandalye", "Sehpa", "Raf", "Askı", "Yapışkanlı Askı",
    "Kapı Askı", "Çerçeve", "Saksı", "Mumluk", "Mum",
    "Kavanoz", "Vazo", "Sürahi", "Bardak", "Fincan",
    "Tabak", "Kase", "Sofra", "Çatal", "Kaşık", "Su Bardağı",
    "Çay Bardağı", "Çay Tabağı", "Meşrubat Bardağı",
    "Rakı Bardağı", "Şarap Kadehi", "Su Takımı", "Çay Takımı",
    "Fincan Takımı", "Kupa", "Şekerlik", "Yağlık", "Tuzluk",
    "Küllük", "Termos", "Mug", "Magnet", "Priz",
    # Small appliances
    "Tost Makinesi", "Mikser", "Kahve Makinesi", "Çay Makinesi",
    "Çaydanlık", "Kettle", "French Press", "Kahve Değirmeni",
    "Narenciye Sıkacağı", "Katı Meyve Sıkacağı",
    "Vantilatör", "Isıtıcı", "Su Sebili",
    "Hava Temizleyici", "Led Işık",
    # Cleaning tools
    "Plastik Kova", "Pazar Arabası", "Ütü Masası",
    "Çivi Ve Vidalama", "Yapıştırıcı", "İzolasyon",
    "İp, Halat", "Kilit Ve Emniyet", "Koli Bandı", "Isı Bandı",
]

_TUIK_09_KEYWORDS = [
    # Entertainment, recreation, sports, culture
    "Kitap", "Dergi", "Oyuncak", "Oyun", "Puzzle", "Robot",
    "Scooter", "Top ", "Toplar", "Spor Aksesuar", "Spor Oyun",
    "Kamp", "Uyku Tulumu", "Pilates",
    "Plaj Oyuncak", "Yazlık Oyuncak", "Uzaktan Kumanda", "Yapı Oyuncak",
    "Peluş", "Oyuncak Bebek", "Oyuncak Silah",
    "Şapka ve Maske", "Oyun Hamuru", "Oyun Konsol", "Oyun Çadır",
    "Kutu Oyun", "Kız Çocuk Oyun",
    "Çizgi Roman", "Öykü", "Masal",
    "Kültür", "Sanat", "Gezi", "Hobi", "Mizah",
    "Gençlik Kitap", "Sağlık Kitap", "Özel Çocuk Kitap",
    "Kişisel Gelişim", "İş Dünyası", "Araştırma", "Bilim",
    "Boyama", "Çocuk Dergi", "Gazeteler", "Magazin",
    "Yemek Dergisi", "Kadın Dergi", "Oto Dergisi", "Özel Dergi",
    # Outdoor / leisure
    "Şezlong", "Salıncak", "Mangal", "Odun", "Kömür",
    "Tutuşturucu", "Piknik", "Çadır",
    "Şişme Havuz", "Mayo", "Pareo", "Deniz Yatak",
    "Kolluk", "Simit", "Yelek",
]

_TUIK_06_KEYWORDS = [
    # Health
    "İlk Yardım", "Hasta Bakım", "Takviye Edici",
    "Sporcu Takviye", "Özel Beslenme",
]

_TUIK_08_KEYWORDS = [
    # Information & communication
    "Telefon", "Tablet", "HDMI", "Kulaklık", "Televizyon",
    "Müzik Sistem", "Pil",
]

_TUIK_02_KEYWORDS = [
    # Alcoholic beverages & tobacco
    "Malt İçeceği",
]

_TUIK_07_KEYWORDS = [
    # Transport-related
    "Oto Aksesuar", "Oto Bakım", "Oto Emniyet", "Oto Kokusu",
]

_TUIK_03_KEYWORDS = [
    # Clothing items sold at Migros
    "Kadın Giyim", "Çocuk Giyim", "Erkek Giyim",
    "Kadın Ev Giyim", "Çocuk Ev Giyim",
    "İç Giyim", "Kadın Atlet", "Erkek Atlet",
    "Kadın Slip", "Kadın Paketli",
    "Kadın Terlik", "Çocuk Terlik", "Kadın Deniz Ayakkabı",
    "Çocuk Deniz Ayakkabı",
    "Kadın Çorap", "Çocuk Çorap", "Kadın Patik", "Kadın Soket",
    "Kadın Termal", "Paketli Külotlu", "Külotlu İnce",
    "Seyahat Aksesuar", "Valiz", "Çantalar", "Giyilebilir Aksesuar",
    "Toka",
]


def migros_category_to_tuik(category_name):
    """Map a Migros product category string to a TUIK group code."""
    if not category_name or not isinstance(category_name, str):
        return "01"  # default: food

    cat = category_name.strip()

    # Check each TUIK group in order of specificity
    for kw in _TUIK_12_KEYWORDS:
        if kw.lower() in cat.lower():
            return "12"
    for kw in _TUIK_05_KEYWORDS:
        if kw.lower() in cat.lower():
            return "05"
    for kw in _TUIK_09_KEYWORDS:
        if kw.lower() in cat.lower():
            return "09"
    for kw in _TUIK_06_KEYWORDS:
        if kw.lower() in cat.lower():
            return "06"
    for kw in _TUIK_08_KEYWORDS:
        if kw.lower() in cat.lower():
            return "08"
    for kw in _TUIK_07_KEYWORDS:
        if kw.lower() in cat.lower():
            return "07"
    for kw in _TUIK_02_KEYWORDS:
        if kw.lower() in cat.lower():
            return "02"
    for kw in _TUIK_03_KEYWORDS:
        if kw.lower() in cat.lower():
            return "03"

    # Default: food & non-alcoholic beverages
    return "01"
