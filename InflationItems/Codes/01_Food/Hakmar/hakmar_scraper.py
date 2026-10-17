# -*- coding: utf-8 -*-
"""
Hakmar Express - Gıda ve alkolsüz içecek fiyat scraper'ı (API ile, tarayıcısız)

Konum:       Bu dosya repoda InflationItems/Codes/01_Food/Hakmar/ klasöründe durmalı.

Çıktı:
  InflationItems/Datas/01_Food/Hakmar/hakmar_YYYY-MM-DD.csv
  -> price_name, price, category_number, subcategory_number
"""
import datetime
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

API = "https://api.hakmarexpress.com.tr/api"
TODAY = datetime.date.today().isoformat()

# Script repoda InflationItems/Codes/01_Food/Hakmar/ içinde durur;
# CSV, InflationItems/Datas/01_Food/Hakmar/ içine hakmar_YYYY-MM-DD.csv olarak yazılır.
ITEMS_ROOT = Path(__file__).resolve().parents[3]          # .../InflationItems
DATA_DIR = ITEMS_ROOT / "Datas" / "01_Food" / "Hakmar"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = DATA_DIR / f"hakmar_{TODAY}.csv"

# True yapılırsa kontrol için iki ek dosya da yazılır (repoya yüklemen gerekmez)
SAVE_EXTRA_FILES = False
DETAIL_CSV = DATA_DIR / f"hakmar_detayli_{TODAY}.csv"
CHOICE_CSV = DATA_DIR / "hakmar_kategori_secimi.csv"
SLEEP = 0.5
MAX_PAGES = 60

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Origin": "https://www.hakmarexpress.com.tr",
    "Referer": "https://www.hakmarexpress.com.tr/",
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
}

# Bu kelimeleri içeren ANA kategoriler tamamen dışarıda kalır
MAIN_EXCLUDE = ["temizlik", "deterjan", "kisisel bakim", "kozmetik", "kagit", "ev",
                "evcil", "pet", "kedi", "kopek", "alkol", "sigara", "tutun", "kirtasiye",
                "elektronik", "oyuncak", "hirdavat", "tekstil", "giyim"]
# Bu kelimeleri içeren ALT kategoriler dışarıda kalır (ör. Bebek > Bebek Bezi)
LEAF_EXCLUDE = MAIN_EXCLUDE + ["bira", "sarap", "raki", "viski", "votka", "bezi", "bezleri", "mendil",
                               "sampuan", "bakim", "sac", "dis", "agiz", "parfum",
                               "deodorant", "tiras", "makyaj", "banyo", "camasir",
                               "bulasik", "hijyen", "pil", "ampul", "aksesuar", "pamuk"]

# Ana ürün listesi dışındaki "önerilen ürünler" bölümleri
SKIP_COMPONENTS = {"products-with-sections"}

session = requests.Session()
session.headers.update(HEADERS)


# ---------- yardımcılar ----------
def norm(s):
    s = (s or "").replace("I", "ı").replace("İ", "i").lower()
    for a, b in zip("çğıöşüâî", "cgiosuai"):
        s = s.replace(a, b)
    return " ".join(re.split(r"[^a-z0-9]+", s)).strip()


def has_kw(text, kws):
    padded = f" {norm(text)} "
    words = padded.split()
    for kw in kws:
        if " " in kw:
            if f" {kw} " in padded:
                return True
        elif any((w.startswith(kw) if len(kw) >= 4 else w == kw) for w in words):
            return True
    return False


def get_json(path, extra_headers=None):
    for attempt in range(3):
        try:
            r = session.get(f"{API}/{path}", headers=extra_headers or {}, timeout=30)
            if r.status_code == 200:
                return r.json()
            print(f"    ! HTTP {r.status_code}: {path}")
        except Exception as e:
            print(f"    ! Hata ({attempt + 1}/3): {e}")
        time.sleep(2)
    return None


# ---------- TÜİK alt kategori eşleştirmesi ----------
# Her site kategorisi için kurallar sırayla denenir, ilk eşleşen kod yazılır.
# "a+b" = ürün adında hem a hem b geçmeli. "*" = kategori içindeki varsayılan kod.
# Hiçbir kurala uymayan ya da TÜİK listesinde karşılığı olmayan ürünler 0 alır.
SUBCAT_RULES = {
    "Sebze": [("lahana", "0117123"), ("carliston", "0117211"), ("biber", "0117215"),
              ("dereotu", "0119401"), ("maydanoz", "0119401"), ("maydonoz", "0119401"),
              ("domates", "0117241"), ("fasulye", "0117312"), ("gobek", "0117141"),
              ("kivircik", "0117141"), ("marul", "0117141"), ("ispanak", "0117151"),
              ("havuc", "0117410"), ("kabak", "0117253"), ("karnabahar", "0117131"),
              ("limon", "0116221"), ("yesil sogan", "0"), ("sogan", "0117431"),
              ("patates", "0117511"), ("patlican", "0117234"), ("mantar", "0117452"),
              ("salatalik", "0117222"), ("pirasa", "0117445"), ("turp", "0117416"),
              ("sarimsak", "0117421"), ("*", "0")],
    "Meyve": [("elma", "0116311"), ("muz", "0116121"), ("mandalina", "0116241"),
              ("portakal", "0116231"), ("nar", "0116591"), ("armut", "0116321"),
              ("ayva", "0116321"), ("uzum", "0116511"), ("seftali", "0116351"),
              ("cilek", "0116451"), ("kivi", "0116521"), ("kavun", "0116531"),
              ("karpuz", "0116541"), ("limon", "0116221"), ("*", "0")],
    "Beyaz Et": [("ciger", "0112401"), ("doner", "0112590"), ("*", "0112246")],
    "Kırmızı Et": [("kofte", "0112593"), ("*", "0112214")],
    "Et Şarküteri": [("sucuk", "0112311"), ("sosis", "0112511"), ("pilic+salam", "0112392"),
                     ("hindi+salam", "0112392"), ("salam", "0112312"),
                     ("kavurma", "0112593"), ("*", "0")],
    "Bal": [("*", "0118313")],
    "Helva, Tahin & Pekmez": [("tahin ve pekmez", "0"), ("petek", "0118313"),
                              ("pekmez", "0118397"), ("tahin", "0118408"),
                              ("peynir helva", "0"), ("kagit helva", "0"),
                              ("cekme helva", "0"), ("helva", "0118916"), ("*", "0")],
    "Kahvaltılık Gevrek": [("*", "0111401")],
    "Krem Çikolata & Ezmeler": [("fistik ezme", "0"), ("kakao", "0118593"),
                                ("nutella", "0118593"), ("krem", "0118593"),
                                ("findik ezme", "0118401"), ("*", "0")],
    "Peynir": [("krem", "0114504"), ("labne", "0114504"), ("ucgen", "0114504"),
               ("tulum", "0114503"), ("kasar", "0114502"), ("tost", "0114502"),
               ("kaskaval", "0114502"), ("cecil", "0114505"), ("orgu", "0114505"),
               ("tel", "0114505"), ("burgu", "0114505"), ("topi", "0114505"),
               ("lor", "0114505"), ("tava", "0114505"), ("anadolu", "0114505"),
               ("beyaz", "0114501"), ("ezine", "0114501"), ("salamura", "0114501"),
               ("surbeni", "0114501"), ("suzme", "0114501"),
               ("olgunlastirilmis", "0114501"), ("lokum", "0114501"), ("*", "0")],
    "Reçel & Marmelat": [("*", "0118391")],
    "Süt": [("devam sutu", "0"), ("cilek", "0114703"), ("kakao", "0114703"),
            ("muz", "0114703"), ("cikolata", "0114703"), ("icimino", "0114703"),
            ("kido", "0114703"), ("aroma", "0114703"), ("yarim yagli", "0114201"),
            ("1 5 yagli", "0114201"), ("0 5 yagli", "0114201"),
            ("2 5 yagli", "0114201"), ("*", "0114111")],
    "Tereyağı": [("*", "0115211")],
    "Yoğurt": [("puding", "0114701"), ("*", "0114601")],
    "Yumurta": [("*", "0114811")],
    "Zeytin": [("*", "0117476")],
    "Kaymak & Krema": [("pasta kremasi", "0119904"), ("*", "0114331")],
    "Margarin": [("*", "0115301")],
    "Fırından": [("kruvasan", "0111392"), ("kek", "0111392"), ("kizarmis ekmek", "0"),
                 ("simit", "0111399"), ("ekme", "0111311"), ("lavas", "0111311"),
                 ("tortilla", "0111311"), ("hamburger", "0111311"),
                 ("sandvic", "0111311"), ("denge", "0111311"), ("*", "0")],
    "Kuruyemiş": [("leblebi sekeri", "0"), ("karisik", "0"), ("kokteyl", "0"),
                  ("favori", "0"), ("kaju", "0"), ("antep fisti", "0116854"),
                  ("fisti", "0116886"), ("ceviz", "0116862"), ("badem", "0116811"),
                  ("findik", "0116843"), ("kabak cekirdeg", "0116891"),
                  ("leblebi", "0116897"), ("cekirdek", "0116898"),
                  ("aycekirdeg", "0116898"), ("*", "0")],
    "Cips": [("fisti", "0116886"), ("patlamis", "0"), ("*", "0117998")],
    "Çikolata, Gofret & Bar": [("protein", "0"), ("tahil bar", "0"), ("yulaf", "0"),
                               ("corny", "0"), ("nesfit", "0"), ("mixmey", "0"),
                               ("delly", "0"), ("tadimca", "0"), ("meyve bar", "0"),
                               ("koz helva", "0"), ("krem cikolata", "0118593"),
                               ("findik kremasi", "0118593"), ("cokokrem", "0118593"),
                               ("sut burger", "0111392"), ("kek", "0111392"),
                               ("pingui", "0111392"), ("bisk", "0111393"),
                               ("kraker", "0111394"), ("gofret", "0111396"),
                               ("gofrik", "0111396"), ("gofibon", "0111396"),
                               ("wafer", "0111396"), ("kitkat", "0111396"),
                               ("dido", "0111396"), ("cokonat", "0111396"),
                               ("*", "0118512")],
    "Bisküvi & Kek": [("protein", "0"), ("gofret", "0111396"), ("kraker", "0111394"),
                      ("crax", "0111394"), ("cizi", "0111394"), ("kek", "0111392"),
                      ("dankek", "0111392"), ("popkek", "0111392"), ("topkek", "0111392"),
                      ("paykek", "0111392"), ("kruvasan", "0111392"),
                      ("kuruvasan", "0111392"), ("browni", "0111392"),
                      ("donut", "0111392"), ("magma", "0111392"), ("luppo", "0111392"),
                      ("sut dilimi", "0111392"), ("rulo pasta", "0111392"),
                      ("kat kat tat", "0111392"), ("*", "0111393")],
    "Kraker": [("*", "0111394")],
    "Şekerleme": [("kayisi", "0116793"), ("lokum", "0118991"), ("pestil", "0"),
                  ("cokopestil", "0"), ("cevizli sucuk", "0"), ("pismaniye", "0"),
                  ("cezerye", "0"), ("sakiz", "0118994"), ("*", "0118995")],
    "Sakız": [("*", "0118994")],
    "Mısır & Pirinç Patlağı": [("*", "0")],
    "Makarna & Mantı": [("noodle", "0"), ("sehriye", "0111502"),
                        ("manti makarna", "0111501"), ("manti", "0119195"),
                        ("*", "0111501")],
    "Bakliyat": [("pirinc", "0111121"), ("bulgur", "0111192"), ("fasulye", "0117611"),
                 ("nohut", "0117632"), ("mercimek", "0117643"), ("*", "0")],
    "Sıvı Yağ": [("aycicek", "0115112"), ("zeytin", "0115131"), ("*", "0")],
    "Tuz, Baharat & Harç": [("nohut", "0117632"), ("kavurma", "0112593"),
                            ("limon tuzu", "0"), ("tuz", "0119311"),
                            ("karbonat", "0119902"), ("kus uzum", "0116711"),
                            ("hindistan cevizi", "0"), ("*", "0119402")],
    "Bulyon": [("*", "0")],
    "Meze, Hazır Yemek & Donuk": [("corba", "0119161"), ("su boreg", "0119192"),
                                  ("pizza", "0119145"), ("pilic", "0112590"),
                                  ("nugget", "0112590"), ("schnitzel", "0112590"),
                                  ("cig kofte", "0119195"), ("icli kofte", "0119195"),
                                  ("kuru patlican", "0"), ("doner", "0112593"),
                                  ("kofte", "0112593"), ("borek", "0119195"),
                                  ("manti", "0119195"), ("hingel", "0119195"),
                                  ("sarma", "0119195"), ("dolma", "0119195"),
                                  ("pilaki", "0119195"), ("lahmacun", "0119195"),
                                  ("salata", "0119195"), ("sandvic", "0119195"),
                                  ("pasta", "0111392"), ("tiramisu", "0111392"),
                                  ("trilece", "0111392"), ("sufle", "0111392"),
                                  ("haslanmis", "0117923"), ("*", "0")],
    "Sos": [("ketcap+mayonez", "0"), ("domates rende", "0117923"),
            ("ketcap", "0119396"), ("mayonez", "0119397"), ("sirke", "0119393"),
            ("*", "0")],
    "Un": [("galeta", "0"), ("pirinc", "0"), ("misir", "0"), ("*", "0111211")],
    "Şeker": [("kup", "0118122"), ("*", "0118121")],
    "Sağlıklı Yaşam Ürünleri": [("*", "0")],
    "Kuru Meyve & Sebze": [("uzum", "0116711"), ("hurma", "0116791"),
                           ("kayisi", "0116793"), ("*", "0")],
    "Konserve": [("ton", "0113315"), ("tursu", "0117992"), ("biber salca", "0"),
                 ("salca", "0117995"), ("hazir yemek", "0119195"), ("*", "0117923")],
    "Tatlı & Pasta Malzemeleri": [("danette", "0114701"), ("dolcia", "0114701"),
                                  ("puding", "0119904"), ("profiterol", "0111392"),
                                  ("sutlac", "0114701"), ("kazandibi", "0114701"),
                                  ("sutlu tatli", "0114701"), ("kabartma", "0119902"),
                                  ("maya", "0119902"), ("karbonat", "0119902"),
                                  ("santi", "0119904"), ("jel", "0119904"),
                                  ("pastaci kremasi", "0119904"), ("pasta", "0111392"),
                                  ("ekler", "0111392"), ("*", "0")],
    "Çay": [("*", "0123021")],
    "Kahve & Toz İçecek": [("krema", "0"), ("soguk kahve", "0"), ("salep", "0"),
                           ("limon", "0"), ("turk kahve", "0122011"),
                           ("filtre", "0122011"), ("*", "0122012")],
    "Enerji İçeceği": [("*", "0126002")],
    "Maden Suyu": [("*", "0125002")],
    "Gazsız İçecek": [("kefir", "0"), ("ayran", "0114605"), ("salgam", "0"),
                      ("soguk cay", "0123034"), ("ice tea", "0123034"),
                      ("fuse", "0123034"), ("bubble", "0"), ("limonata", "0126002"),
                      ("multi vitamin", "0126002"), ("*", "0121001")],
    "Gazlı İçecek": [("kola", "0126003"), ("cola", "0126003"), ("pepsi", "0126003"),
                     ("*", "0126002")],
    "Su": [("*", "0125001")],
    "Dondurma": [("kulah", "0"), ("*", "0118601")],
    "Bebek Maması": [("bebek sutu", "0119212"), ("devam sutu", "0119212"), ("*", "0")],
}
_RULES = {norm(k): v for k, v in SUBCAT_RULES.items()}


def _kw_in(kw, padded_name):
    return all(f" {part}" in padded_name for part in kw.split("+"))


def assign_subcategory(leaf_category, product_name):
    """Ürünün TÜİK 7 haneli kodunu döndürür; karşılık yoksa '0'."""
    rules = _RULES.get(norm(leaf_category))
    if not rules:
        return "0"
    padded = f" {norm(product_name)}"
    for kw, code in rules:
        if kw == "*" or _kw_in(kw, padded):
            return code
    return "0"


# ---------- kategoriler ----------
def get_leaf_categories():
    data = get_json("home/initialize-v2")
    if not data:
        raise SystemExit("Kategori listesi alınamadı.")
    mains = data.get("category", {}).get("mainCategories", [])

    leaves = []

    def collect(cat, main_name, path):
        subs = cat.get("categories") or []
        if not subs:
            leaves.append({"main": main_name, "leaf": cat["name"], "path": path,
                           "slug": cat["slug"], "count": cat.get("productCount") or 0})
        for s in subs:
            collect(s, main_name, f"{path} > {s['name']}")

    for m in mains:
        if m.get("isDivider"):
            continue
        collect(m, m["name"], m["name"])

    rows = []
    for c in leaves:
        if has_kw(c["main"], MAIN_EXCLUDE):
            c["secildi"], c["neden"] = False, "ana kategori gıda dışı"
        elif has_kw(c["leaf"], LEAF_EXCLUDE):
            c["secildi"], c["neden"] = False, "alt kategori gıda dışı"
        else:
            c["secildi"], c["neden"] = True, ""
        rows.append(c)

    if SAVE_EXTRA_FILES:
        pd.DataFrame(rows)[["secildi", "path", "slug", "count", "neden"]].to_csv(
            CHOICE_CSV, index=False, encoding="utf-8-sig")
    return [c for c in rows if c["secildi"]], rows


# ---------- ürünler ----------
def find_cards(obj, out, skip_sections):
    if isinstance(obj, dict):
        if skip_sections and obj.get("component") in SKIP_COMPONENTS:
            return
        if obj.get("component") == "product-card" and isinstance(obj.get("product"), dict):
            out.append(obj["product"])
            return
        for v in obj.values():
            find_cards(v, out, skip_sections)
    elif isinstance(obj, list):
        for v in obj:
            find_cards(v, out, skip_sections)


def fetch_category(cat):
    slug = cat["slug"]
    products, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        data = get_json(f"home/slug/{slug}?", {
            "x-encoded-url": quote(f"{slug}?", safe=""),
            "x-page-number": str(page),
        })
        if not data:
            break
        cards = []
        find_cards(data, cards, skip_sections=True)
        if not cards and page == 1:
            find_cards(data, cards, skip_sections=False)
            if not cards:
                with open(f"debug_{slug}.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                print(f"    ! Ürün bulunamadı, debug_{slug}.json kaydedildi")
        new = [p for p in cards if p.get("id") not in seen]
        if not new:
            break
        for p in new:
            seen.add(p.get("id"))
            products.append(p)
        if cat["count"] and len(products) >= cat["count"]:
            break
        time.sleep(SLEEP)
    return products


def main():
    start = time.time()
    print("=" * 60)
    print(f"  Hakmar Express Gıda Scraper  |  {TODAY}")
    print("=" * 60)

    selected, all_leaves = get_leaf_categories()
    print(f"\n{len(all_leaves)} alt kategori bulundu, {len(selected)} tanesi gıda/içecek olarak seçildi.")
    print()

    rows, seen_ids = [], set()
    for i, cat in enumerate(selected, 1):
        items = fetch_category(cat)
        added = 0
        for p in items:
            pid = p.get("id")
            if pid in seen_ids or p.get("price") is None:
                continue
            seen_ids.add(pid)
            added += 1
            rows.append({
                "price_name": (p.get("name") or "").strip(),
                "price": float(p["price"]),
                "category_number": 1,
                "subcategory_number": assign_subcategory(cat["leaf"], p.get("name") or ""),
                "ana_kategori": cat["main"],
                "alt_kategori": cat["leaf"],
                "urun_id": pid,
                "barkod": p.get("barcode"),
                "eski_fiyat": p.get("oldPrice"),
                "kg_fiyati": p.get("pricePerKg"),
                "birim": p.get("unitCode"),
                "stokta_yok": p.get("outOfStock"),
                "url": f"https://www.hakmarexpress.com.tr/{p.get('slug', '')}",
                "tarih": TODAY,
            })
        flag = "" if not cat["count"] or len(items) >= cat["count"] else "  <- beklenenden az"
        print(f"[{i}/{len(selected)}] {cat['path']}: {len(items)}/{cat['count']} ürün, {added} yeni{flag}")
        time.sleep(SLEEP)

    if not rows:
        print("\nHiç ürün bulunamadı.")
        return

    df = pd.DataFrame(rows)
    df[["price_name", "price", "category_number", "subcategory_number"]].to_csv(
        OUT_CSV, index=False, encoding="utf-8-sig")
    if SAVE_EXTRA_FILES:
        df.to_csv(DETAIL_CSV, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 60)
    print(f"  Toplam ürün : {len(df)}")
    print(f"  Dosya       : {OUT_CSV}")
    print(f"  Süre        : {time.time() - start:.0f} sn")
    print("=" * 60)


if __name__ == "__main__":
    main()
