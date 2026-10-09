from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
import re
from datetime import datetime

BASE_DOMAIN = "https://www.addax.com.tr"
today = datetime.now().strftime("%Y-%m-%d")
OUTPUT_FILE = f"addax_urunler_{today}.csv"

CATEGORIES = [
    "yeni-urunler",
    "ust-giyim",
    "alt-giyim",
    "dis-giyim",
]

PRODUCT_CARD_SELECTOR = "div[data-productitemlayout]"
MAX_ROUNDS_WITHOUT_NEW = 8
MAX_TOTAL_ROUNDS = 500
SCROLL_PAUSE = 1.2


def log(msg):
    print(f"[INFO] {msg}")


def ok(msg):
    print(f"[OK] {msg}")


def warn(msg):
    print(f"[UYARI] {msg}")


def setup_driver():
    log("Chrome driver başlatılıyor...")

    options = Options()
    options.add_argument("--start-maximized")
    # options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-infobars")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    ok("Driver hazır.")
    return driver


def build_category_url(category_slug):
    return f"{BASE_DOMAIN}/{category_slug}"


def get_cards_data(driver):
    script = """
    return [...document.querySelectorAll("div[data-productitemlayout]")].map((el, idx) => ({
        idx,
        text: (el.innerText || "").trim(),
        product_id: el.getAttribute("data-id") || "",
        barcode: el.getAttribute("data-barcode") || "",
        top: el.getBoundingClientRect().top,
        bottom: el.getBoundingClientRect().bottom,
        height: el.getBoundingClientRect().height
    }));
    """
    return driver.execute_script(script)


def parse_card_text(raw_text):
    if not raw_text:
        return None

    text = raw_text.replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    if not lines:
        return None

    full = " | ".join(lines)

    price_match = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}\s*TL)", full)
    if not price_match:
        return None

    price = price_match.group(1).strip()

    junk_patterns = [
        r"^BEDEN$",
        r"^EKLE$",
        r"^[SMLX\s]+$",
        r"^\+\d+\s*Renk$",
        r"^\d{1,3}(?:\.\d{3})*,\d{2}\s*TL$",
    ]

    cleaned = []
    for line in lines:
        skip = False
        for pat in junk_patterns:
            if re.match(pat, line, flags=re.IGNORECASE):
                skip = True
                break
        if not skip:
            cleaned.append(line)

    name = ""
    for line in reversed(cleaned):
        if re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}\s*TL", line, flags=re.IGNORECASE):
            continue
        if "renk" in line.lower():
            continue
        if len(line) >= 4:
            name = line.strip()
            break

    if not name:
        return None

    return {
        "urun_ismi": name,
        "fiyat": price
    }


def collect_visible_products(driver, category_slug, seen_keys, collected_rows):
    cards = get_cards_data(driver)
    log(f"DOM'da görülen kart sayısı: {len(cards)}")

    new_count = 0

    for card in cards:
        parsed = parse_card_text(card.get("text", ""))
        if not parsed:
            continue

        product_id = (card.get("product_id") or "").strip()
        barcode = (card.get("barcode") or "").strip()

        # Öncelik gerçek ürün kimliklerinde
        if product_id or barcode:
            unique_key = (
                category_slug.strip().lower(),
                product_id,
                barcode
            )
        else:
            unique_key = (
                category_slug.strip().lower(),
                parsed["urun_ismi"].strip().lower(),
                parsed["fiyat"].strip().lower()
            )

        if unique_key not in seen_keys:
            seen_keys.add(unique_key)
            collected_rows.append({
                "kategori": category_slug,
                "urun_id": product_id,
                "barcode": barcode,
                "urun_ismi": parsed["urun_ismi"],
                "fiyat": parsed["fiyat"]
            })
            new_count += 1
            print(f"   -> {parsed['urun_ismi']} | {parsed['fiyat']} | id={product_id} | barcode={barcode}")

    ok(f"Bu turda eklenen yeni ürün sayısı: {new_count}")
    ok(f"Şu ana kadar toplanan toplam benzersiz ürün: {len(collected_rows)}")

    return cards, new_count


def scroll_to_last_visible_card(driver, previous_last_key=None):
    cards = get_cards_data(driver)
    if not cards:
        return None

    # Ekranda görünen son kart: top değeri en büyük olan
    visible_cards = [c for c in cards if c["bottom"] > 0 and c["height"] > 0]

    if not visible_cards:
        visible_cards = cards

    last_card = max(visible_cards, key=lambda x: x["top"])

    last_key = (
        (last_card.get("product_id") or "").strip(),
        (last_card.get("barcode") or "").strip(),
        (last_card.get("text") or "").strip()[:120]
    )

    log(f"Son görünen karta ilerleniyor: key={last_key}")

    # Aynı karta takılı kaldıysa biraz daha agresif davran
    if previous_last_key is not None and last_key == previous_last_key:
        log("Aynı son karta takılındı, ekstra aşağı itme deneniyor...")
        driver.execute_script("""
            const cards = document.querySelectorAll("div[data-productitemlayout]");
            if (cards.length) {
                cards[cards.length - 1].scrollIntoView({block: 'end', behavior: 'instant'});
                window.scrollBy(0, 250);
            }
        """)
    else:
        driver.execute_script("""
            const cards = document.querySelectorAll("div[data-productitemlayout]");
            if (cards.length) {
                cards[cards.length - 1].scrollIntoView({block: 'end', behavior: 'instant'});
            }
        """)

    time.sleep(SCROLL_PAUSE)
    return last_key


def scrape_category(driver, category_slug):
    log("=" * 70)
    log(f"Kategori taranıyor: {category_slug}")

    url = build_category_url(category_slug)
    log(f"Sayfa açılıyor: {url}")

    driver.get(url)
    time.sleep(4)

    seen_keys = set()
    collected_rows = []

    rounds_without_new = 0
    previous_last_key = None

    for round_no in range(1, MAX_TOTAL_ROUNDS + 1):
        log(f"Tur {round_no} başladı")

        _, new_count = collect_visible_products(
            driver=driver,
            category_slug=category_slug,
            seen_keys=seen_keys,
            collected_rows=collected_rows
        )

        if new_count == 0:
            rounds_without_new += 1
        else:
            rounds_without_new = 0

        if rounds_without_new >= MAX_ROUNDS_WITHOUT_NEW:
            log("Uzun süredir yeni ürün gelmiyor. Kategori sonlandırıldı.")
            break

        new_last_key = scroll_to_last_visible_card(driver, previous_last_key=previous_last_key)

        if new_last_key is None:
            warn("Scroll için kart bulunamadı.")
            break

        previous_last_key = new_last_key

    ok(f"{category_slug} kategorisinden toplam {len(collected_rows)} ürün toplandı.")
    return collected_rows


def deduplicate(rows):
    log("Genel tekrar temizliği yapılıyor...")

    seen = set()
    unique_rows = []

    for row in rows:
        key = (
            row["kategori"].strip().lower(),
            row["urun_id"].strip(),
            row["barcode"].strip(),
            row["urun_ismi"].strip().lower(),
            row["fiyat"].strip().lower()
        )
        if key not in seen:
            seen.add(key)
            unique_rows.append(row)

    ok(f"Genel benzersiz kayıt sayısı: {len(unique_rows)}")
    return unique_rows


def write_csv(rows, filename):
    log(f"CSV yazılıyor: {filename}")

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["kategori", "urun_id", "barcode", "urun_ismi", "fiyat"]
        )
        writer.writeheader()
        writer.writerows(rows)

    ok("CSV başarıyla oluşturuldu.")


def main():
    if not CATEGORIES:
        warn("CATEGORIES boş. Önce kategori sluglarını gir.")
        return

    log("Addax scraper başlatıldı.")
    log(f"Toplam kategori sayısı: {len(CATEGORIES)}")

    driver = setup_driver()

    try:
        all_rows = []

        for idx, category_slug in enumerate(CATEGORIES, start=1):
            log(f"[{idx}/{len(CATEGORIES)}] kategori işleniyor...")
            category_rows = scrape_category(driver, category_slug)
            all_rows.extend(category_rows)
            ok(f"Şu ana kadar toplanan toplam kayıt: {len(all_rows)}")

        if not all_rows:
            warn("Hiç veri toplanamadı.")
            return

        unique_rows = deduplicate(all_rows)
        write_csv(unique_rows, OUTPUT_FILE)

        ok(f"İşlem tamamlandı. Toplam benzersiz ürün sayısı: {len(unique_rows)}")
        ok(f"Dosya aynı klasöre yazıldı: {OUTPUT_FILE}")

    except Exception as e:
        warn(f"Hata oluştu: {e}")

    finally:
        log("Driver kapatılıyor...")
        driver.quit()
        ok("Program sonlandı.")


if __name__ == "__main__":
    main()