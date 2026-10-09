import os
import re
import time
import random
import pandas as pd
from datetime import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

# =========================
# CONFIG
# =========================
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA_PATH = r"C:\Users\SEDA\Desktop\TeknosaChromeProfile"
OUTPUT_FOLDER = r"C:\Users\SEDA\OneDrive - ozyegin.edu.tr\Desktop\ai201\Teknosa\Datas"

BASE_URL = "https://www.teknosa.com/hirdavat-yapi-market-c-115006"
MAX_PAGES = 400
LOCAL_PORT = 9444


# =========================
# HELPERS
# =========================
def clean_price(text):
    if not text:
        return None
    text = text.replace("TL", "").replace("₺", "").strip()
    text = text.replace(".", "").replace(",", ".")
    text = re.sub(r"[^\d.]", "", text)
    try:
        return float(text) if text else None
    except:
        return None


def build_browser():
    os.makedirs(USER_DATA_PATH, exist_ok=True)

    co = ChromiumOptions()
    co.set_browser_path(CHROME_PATH)
    co.set_user_data_path(USER_DATA_PATH)
    co.set_paths(local_port=LOCAL_PORT)
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--start-maximized")
    co.set_argument("--no-first-run")
    co.set_argument("--no-default-browser-check")

    page = ChromiumPage(co)
    try:
        page.set.headers({"Referer": "https://www.google.com/"})
    except:
        pass
    return page


def short_sleep(a=0.6, b=1.2):
    time.sleep(random.uniform(a, b))


def get_body_text(page):
    try:
        body = page.ele('tag:body')
        return body.text if body else ""
    except:
        return ""


def click_if_exists(page, texts):
    for txt in texts:
        selectors = [
            f'xpath://button[contains(., "{txt}")]',
            f'xpath://a[contains(., "{txt}")]',
            f'xpath://div[contains(., "{txt}")]',
            f'xpath://span[contains(., "{txt}")]',
        ]
        for sel in selectors:
            try:
                ele = page.ele(sel, timeout=1)
                if ele:
                    ele.click(by_js=True)
                    return True
            except:
                pass
    return False


def handle_popups_once(page):
    popup_texts = [
        "Tümünü Kabul Et",
        "Kabul Et",
        "Anladım",
        "Daha Sonra",
        "Kapat",
        "Tamam",
        "İzin Ver",
        "Vazgeç"
    ]
    for _ in range(3):
        if not click_if_exists(page, popup_texts):
            break
        short_sleep(0.5, 0.9)


def save_debug(page, page_num, page_text):
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    html_path = os.path.join(OUTPUT_FOLDER, f"debug_page_{page_num}.html")
    txt_path = os.path.join(OUTPUT_FOLDER, f"debug_page_{page_num}.txt")

    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.html or "")
    except:
        pass

    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(page_text or "")
    except:
        pass

    print(f"[DEBUG] Saved HTML: {html_path}")
    print(f"[DEBUG] Saved TXT : {txt_path}")


# =========================
# TEXT PARSING
# =========================
def is_price_line(line):
    line = line.strip()
    return bool(re.fullmatch(r'\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*TL', line))


def is_range_or_filter_line(line):
    line_low = line.lower()
    return (
        "tl arası" in line_low
        or "tl üzeri" in line_low
        or "fiyat aralığı" in line_low
        or re.search(r"\(\d+\)", line_low) is not None
    )


def is_installment_line(line):
    line_low = line.strip().lower()
    return (
        "peşin fiyatına" in line_low
        or "pesin fiyatina" in line_low
        or (" x " in f" {line_low} " and "tl" in line_low)
    )


def looks_like_product_name(line):
    line = line.strip()

    bad_contains = [
        "Sipariş Takibi",
        "Alışveriş Kredisi",
        "Mağazalarımız",
        "Yardım Merkezi",
        "Kurumsal Satış",
        "Teknosa Blog",
        "Pazaryeri",
        "Tüm Ürünler",
        "Görselle Ara",
        "Sesli Ara",
        "Temizle",
        "Trend Aramalar",
        "Popüler Kategoriler",
        "Öne Çıkan Markalar",
        "Haftanın En Popüler Ürünleri",
        "Kategoriler",
        "Markalar",
        "Mağazalar",
        "Giriş Yap",
        "Üye Ol",
        "Sepetim",
        "TeknoClub",
        "Telefon & Aksesuar",
        "Bilgisayar & Tablet",
        "TV, Ses ve Görüntü",
        "Beyaz Eşya",
        "Elektrikli Ev Aletleri",
        "Yenilenmiş Ürünler",
        "Kampanyalar",
        "Outlet",
        "İptal & İade",
        "Arıza ve Onarım Hizmetleri",
        "Kurulum Hizmetleri",
        "Teknoloji Destek Paketleri",
        "Kişiselleştirilmiş Ürünler",
        "Hizmet Üyelik Paketleri",
        "Ek Garanti ve Koruma",
        "Eskisini Getir Yenisini Götür",
        "Bizi Takip Edin",
        "Reklam",
        "Ana Sayfa",
        "Ev ve Yaşam",
        "Hırdavat ve Yapı Market",
        "Sonuç",
        "Sıralama",
        "Önerilenler",
        "Yeni",
        "En Çok Satanlar",
        "En Favoriler",
        "Azalan Fiyat",
        "Artan Fiyat",
        "Karşılaştır",
        "Filtrele",
        "Sırala",
        "Filtreler",
        "Alt Kategoriler",
        "ÜCRETSİZ Kargo",
        "Sepete Ekle",
        "Favori",
        "Teknosa",
    ]

    if not line:
        return False
    if "TL" in line:
        return False
    if len(line) < 5:
        return False
    if line.isdigit():
        return False
    if is_range_or_filter_line(line):
        return False

    for bad in bad_contains:
        if bad.lower() in line.lower():
            return False

    if not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", line):
        return False

    return True


def extract_products_from_text(page_text):
    if not page_text:
        return []

    lines = [x.strip() for x in page_text.splitlines() if x.strip()]
    results = []
    seen = set()

    for i, line in enumerate(lines):
        if not is_price_line(line):
            continue
        if is_range_or_filter_line(line):
            continue

        current_price = clean_price(line)
        if current_price is None:
            continue

        name = None
        for back in range(1, 9):
            j = i - back
            if j < 0:
                break

            candidate = lines[j]

            if is_installment_line(candidate):
                continue
            if is_price_line(candidate):
                continue
            if is_range_or_filter_line(candidate):
                continue

            if looks_like_product_name(candidate):
                name = candidate
                break

        if not name:
            continue

        final_price = current_price
        if i + 1 < len(lines) and is_price_line(lines[i + 1]) and not is_range_or_filter_line(lines[i + 1]):
            next_price = clean_price(lines[i + 1])
            if next_price is not None:
                final_price = max(current_price, next_price)

        key = (name, final_price)
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "Category": "Hırdavat ve Yapı Market",
            "Product_Name": name,
            "Price": final_price,
            "Currency": "TRY",
            "Scraped_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    return results


# =========================
# MAIN
# =========================
def scrape_teknosa_fast():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    page = build_browser()
    all_rows = []
    global_seen = set()

    try:
        for page_num in range(1, MAX_PAGES + 1):
            url = f"{BASE_URL}?page={page_num}"
            print(f"[INFO] Opening page {page_num}: {url}")

            try:
                page.get(url, timeout=40)
                short_sleep(1.0, 1.8)
            except Exception as e:
                print(f"[WARN] Could not open page {page_num}: {e}")
                continue

            if page_num == 1:
                handle_popups_once(page)
                short_sleep(0.5, 1.0)

            page_text = get_body_text(page)

            if page_num == 1:
                save_debug(page, page_num, page_text)
                print("[DEBUG] first 1000 chars:")
                print(page_text[:1000])
                print("-" * 80)

            page_rows = extract_products_from_text(page_text)

            new_rows = []
            for row in page_rows:
                key = (row["Product_Name"], row["Price"])
                if key not in global_seen:
                    global_seen.add(key)
                    new_rows.append(row)

            all_rows.extend(new_rows)
            print(f"[INFO] Page {page_num} | found: {len(page_rows)} | new: {len(new_rows)} | total: {len(global_seen)}")

            # stop when a page contributes no new products
            if page_num > 1 and len(new_rows) == 0:
                print("[INFO] No new products. Stopping.")
                break

        if all_rows:
            df = pd.DataFrame(all_rows)
            df.drop_duplicates(subset=["Category", "Product_Name", "Price"], inplace=True)

            out_path = os.path.join(
                OUTPUT_FOLDER,
                f"teknosa_hirdavat_yapi_market_{datetime.now().strftime('%Y-%m-%d')}.csv"
            )
            df.to_csv(out_path, index=False, encoding="utf-8-sig")

            print(f"\n[SUCCESS] Saved {len(df)} rows")
            print(out_path)
        else:
            print("\n[INFO] No data collected.")

    finally:
        try:
            page.quit()
        except:
            pass


if __name__ == "__main__":
    scrape_teknosa_fast()
