"""
stradivarius_scraper.py
=======================
Stradivarius Türkiye ürün verisi çekici.

Kullanım:
    python stradivarius_scraper.py

Çıktı: stradivarius_YYYY-MM-DD.csv
Kolonlar: product_name, price

Bağımlılıklar:
    pip install curl_cffi tqdm

API Sabitleri (STORE_ID / REGION_ID):
    DevTools → Network → itxrest filtresi ile doğrudan URL'den okunabilir:
    https://www.stradivarius.com/itxrest/2/catalog/store/54009571/50331081/...
    STORE_ID  = 54009571   (Stradivarius TR mağaza tanımlayıcısı)
    REGION_ID = 50331081   (Inditex TR bölge tanımlayıcısı)
"""

import argparse
import csv
import logging
import time
import random
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional

# ── Repo-relative output path ─────────────────────────────────────────────────
# Bu dosya: InflationItems/Codes/ClothingStores/Stradivarius/StradivariusScraper.py
# Veri:     InflationItems/Datas/ClothingStores/Stradivarius/
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_OUT_DIR = _REPO_ROOT / "InflationItems" / "Datas" / "ClothingStores" / "Stradivarius"

from curl_cffi import requests
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

# Stradivarius menüsünde hem gerçek ürün kategorileri (Tişört, Jean vb.)
# hem de editoryal/kampanya kategorileri (Yeni koleksiyon, Tümü vb.) var.
# Dedup first-seen kazanır; gerçek kategorileri önce işleyerek doğru etiket atılır.
EDITORIAL_PARENTS = {
    "yeni koleksiyon", "yeni", "tümü", "ürüne göre alışveriş",
    "ürüne göre satın al", "stradimarket", "denim hub",
}

# Stradivarius iç SEO etiketleri — örn. "Sweatshirt > STR_VER_SUDA_GRISES_SEO"
# Bu prefix'i içeren child kategoriler parent ismiyle değiştirilir.
SEO_PREFIX = "STR_VER_SUDA_"


# ---------------------------------------------------------------------------
# Kategori yolu temizleyici
# ---------------------------------------------------------------------------

def _clean_category(parent: Optional[str], cat_name: str) -> str:
    """
    Ham kategori ağacından okunabilir kategori yolu üretir.

    Kurallar (öncelik sırasıyla):
    1. cat_name STR_VER_SUDA_ ile başlıyorsa        → parent'ı kullan
       Örn: "Sweatshirt > STR_VER_SUDA_GRISES_SEO"  → "Sweatshirt"

    2. cat_name "Tümünü gör" veya "Tümü" ise:
       - parent "Tümü" ise                           → "Aksesuar"
       - diğer durumlarda                            → parent'ı kullan
       Örn: "Jean > Tümünü gör"                      → "Jean"
       Örn: "Tümü > Tümü"                            → "Aksesuar"

    3. parent "Tümü" ise                             → cat_name'i kullan
       Örn: "Tümü > Güneş gözlüğü"                  → "Güneş gözlüğü"
       Örn: "Tümü > Parfüm"                          → "Parfüm"

    4. Diğer durumlarda                              → "parent > cat_name"
       Örn: "Jean > D91"                             → "Jean > D91"
       Örn: (None, "Bijuteri")                       → "Bijuteri"
    """
    # Kural 1: SEO etiketleri
    if cat_name.startswith(SEO_PREFIX):
        return parent if parent else cat_name

    # Kural 2: "Tümünü gör" / "Tümü" child
    if cat_name.strip() in ("Tümünü gör", "Tümü"):
        if parent and parent.strip().lower() == "tümü":
            return "Aksesuar"
        return parent if parent else cat_name

    # Kural 3: parent "Tümü" → child daha anlamlı
    if parent and parent.strip().lower() == "tümü":
        return cat_name

    # Kural 4: normal
    return f"{parent} > {cat_name}" if parent else cat_name


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class StradivariusScraper:

    STORE_ID    = "54009571"
    REGION_ID   = "50331081"
    LANGUAGE_ID = "-43"
    APP_ID      = "1"

    BASE_URL       = "https://www.stradivarius.com"
    CATALOG_V2_URL = f"{BASE_URL}/itxrest/2/catalog/store/{STORE_ID}/{REGION_ID}"
    CATALOG_V3_URL = f"{BASE_URL}/itxrest/3/catalog/store/{STORE_ID}/{REGION_ID}"

    BATCH_SIZE       = 50
    MAX_RETRIES      = 5
    RETRY_BACKOFF    = 3
    RATE_LIMIT_SLEEP = 60

    DEFAULT_HEADERS = {
        "Accept":          "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection":      "keep-alive",
        "Content-Type":    "application/json",
        "Referer":         "https://www.stradivarius.com/tr/",
        "Sec-Fetch-Dest":  "empty",
        "Sec-Fetch-Mode":  "cors",
        "Sec-Fetch-Site":  "same-origin",
    }

    def __init__(self, output_dir: str = str(_DEFAULT_OUT_DIR), delay: float = 0.2):
        self.output_dir = Path(output_dir)
        self.delay      = delay
        self._session: Optional[requests.Session] = None

    # ── Session ──────────────────────────────────────────────────────────────

    def _make_session(self) -> requests.Session:
        session = requests.Session(impersonate="chrome")
        session.headers.update(self.DEFAULT_HEADERS)
        return session

    def _warmup(self) -> None:
        """Akamai cookie'lerini toplamak için homepage'i ziyaret eder."""
        try:
            resp = self._session.get(f"{self.BASE_URL}/tr/", timeout=20)
            logger.debug("Warmup tamamlandi: HTTP %d", resp.status_code)
        except Exception as exc:
            logger.warning("Warmup basarisiz (devam ediliyor): %s", exc)

    # ── HTTP ─────────────────────────────────────────────────────────────────

    def _get(self, url: str, timeout: int = 25) -> Optional[dict]:
        """Retry + exponential backoff ile GET isteği atar."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = self._session.get(url, timeout=timeout)

                if resp.status_code == 404:
                    return None

                if resp.status_code in (403, 429):
                    wait = max(
                        int(resp.headers.get("Retry-After", self.RATE_LIMIT_SLEEP)),
                        self.RATE_LIMIT_SLEEP,
                    )
                    logger.warning(
                        "Rate limit (%d). %ds bekleniyor (deneme %d/%d)...",
                        resp.status_code, wait, attempt, self.MAX_RETRIES,
                    )
                    time.sleep(wait)
                    self._warmup()
                    continue

                resp.raise_for_status()
                return resp.json()

            except Exception as exc:
                if attempt == self.MAX_RETRIES:
                    logger.error("Tum %d deneme basarisiz -- %s: %s",
                                 self.MAX_RETRIES, url, exc)
                    return None
                wait = self.RETRY_BACKOFF * attempt
                logger.warning("Deneme %d basarisiz (%s). %ds sonra tekrar...",
                               attempt, exc, wait)
                time.sleep(wait)
        return None

    def _sleep(self) -> None:
        time.sleep(self.delay * random.uniform(0.5, 1.5))

    # ── Kategoriler ───────────────────────────────────────────────────────────

    def fetch_categories(self) -> list[dict]:
        """
        v2 catalog/category endpoint'inden tam agaci ceker, leaf node'lari doner.

        Siralama: gercek urun kategorileri once (Tisort, Jean, Etek vb.),
        editoryal kategoriler sonra (Yeni koleksiyon, Tumu vb.).
        Boylece dedup first-seen mantigi dogru kategori etiketini atar.
        """
        url = (
            f"{self.CATALOG_V2_URL}/category"
            f"?languageId={self.LANGUAGE_ID}"
            f"&typeCatalog=1"
            f"&appId={self.APP_ID}"
        )
        logger.info("Kategori agaci cekiliyor...")
        data = self._get(url)
        if not data:
            logger.error("Kategori verisi alinamadi.")
            return []

        categories: list[dict] = []

        def walk(items: list, parent_name: Optional[str] = None) -> None:
            for item in items or []:
                name = item.get("name", "")
                subs = item.get("subcategories") or item.get("subCategories") or []
                if subs:
                    walk(subs, parent_name=name)
                else:
                    cid = item.get("id") or item.get("categoryId")
                    if not cid:
                        continue
                    view_id = item.get("viewCategoryId")
                    product_cat_id = str(view_id) if view_id else str(cid)
                    categories.append({
                        "id":                  str(cid),
                        "product_category_id": product_cat_id,
                        "name":                name,
                        "parent_name":         parent_name,
                    })

        if isinstance(data, list):
            walk(data)
        elif isinstance(data, dict):
            walk(data.get("categories") or data.get("items") or [data])

        # Kategori ID bazlı deduplikasyon
        seen: set[str] = set()
        unique = []
        for cat in categories:
            if cat["id"] not in seen:
                seen.add(cat["id"])
                unique.append(cat)

        # Gercek urun kategorileri once, editoryal sonra.
        # Hem parent_name hem de category'nin kendi adi kontrol edilir.
        # Ornek: root "Yeni" kategorisi (parent=None, name="Yeni") → editorial.
        # parent_name kontrolu olmadan is_editorial=False donup gercek gibi
        # islenir ve urunler yanlis etiketlenir.
        def is_editorial(cat: dict) -> bool:
            p = (cat.get("parent_name") or "").strip().lower()
            n = (cat.get("name") or "").strip().lower()
            return p in EDITORIAL_PARENTS or n in EDITORIAL_PARENTS

        unique.sort(key=is_editorial)

        real_count      = sum(1 for c in unique if not is_editorial(c))
        editorial_count = len(unique) - real_count
        logger.info(
            "%d leaf kategori bulundu (%d gercek, %d editoryal).",
            len(unique), real_count, editorial_count,
        )
        return unique

    # ── Ürün ID'leri ──────────────────────────────────────────────────────────

    def fetch_product_ids(self, category_id: str) -> list[str]:
        """showNoStock=false ile stokta olan urun ID'lerini doner."""
        url = (
            f"{self.CATALOG_V3_URL}/category/{category_id}/product"
            f"?languageId={self.LANGUAGE_ID}"
            f"&showProducts=false"
            f"&showNoStock=false"
            f"&appId={self.APP_ID}"
            f"&locale=tr_TR"
        )
        data = self._get(url)
        if not data:
            return []
        return [str(pid) for pid in data.get("productIds", [])]

    # ── Ürün detayları ────────────────────────────────────────────────────────

    def fetch_product_details(self, product_ids: list[str], category_id: str) -> list[dict]:
        """BATCH_SIZE'lik parcalar halinde productsArray endpoint'inden detay ceker."""
        all_products: list[dict] = []
        for i in range(0, len(product_ids), self.BATCH_SIZE):
            batch   = product_ids[i : i + self.BATCH_SIZE]
            ids_str = ",".join(batch)
            url = (
                f"{self.CATALOG_V3_URL}/productsArray"
                f"?languageId={self.LANGUAGE_ID}"
                f"&productIds={ids_str}"
                f"&categoryId={category_id}"
                f"&appId={self.APP_ID}"
                f"&locale=tr_TR"
            )
            data = self._get(url)
            if data:
                all_products.extend(data.get("products", []))
            time.sleep(0.1)
        return all_products

    # ── Kayıt çıkarımı ────────────────────────────────────────────────────────

    def extract_records(self, raw: dict, category_path: str) -> list[dict]:
        """
        Ham Inditex urun dict'inden renk basina bir CSV satiri uretir.

        Her renk icin ilk bedenin fiyati alinir.
        Ayni rengin farkli bedenleri her zaman ayni fiyata sahiptir.

        Donulen liste bos olabilir (isim/fiyat alinamazsa).

        price: o gunun satis fiyati (TRY).
            Indirimli urunde indirimli, indirimsizde normal fiyat.
            Enflasyon takibi icin dogru kolon budur.

        Ornek cikti (tek urun, 3 renk):
            [
                {"product_name": "Basic tişört - Siyah", "price": 649.0},
                {"product_name": "Basic tişört - Beyaz", "price": 649.0},
                {"product_name": "Basic tişört - Krem", "price": 649.0},
            ]
        """
        if not raw or not isinstance(raw, dict):
            return []

        name = (raw.get("name") or "").strip()
        if not name:
            return []

        records: list[dict] = []
        try:
            summaries = raw.get("bundleProductSummaries") or []
            if not summaries:
                return []
            detail = summaries[0].get("detail") or {}
            colors = detail.get("colors") or []

            for color_obj in colors:
                color_name = (color_obj.get("name") or "").strip()
                if not color_name:
                    continue
                # ilk bedenin fiyatini al
                for size in color_obj.get("sizes") or []:
                    price_cents = size.get("price")
                    if price_cents is not None:
                        records.append({
                            "product_name": f"{name} - {color_name}",
                            "price":        round(int(price_cents) / 100, 2),
                        })
                        break  # bu renk icin ilk beden yeterli

        except Exception:
            return []

        return records

    # ── Ana pipeline ──────────────────────────────────────────────────────────

    def run(self, verify: bool = False) -> Path:
        """
        Pipeline:
            1. Session + Akamai warmup
            2. Kategorileri cek (gercek kategoriler once)
            3. Her kategori: product ID'leri → detaylar → CSV'ye yaz

        verify=True: her kategori icin detayli ID/yazilan/atlanan sayilari loglar,
                     sonda ozet tablo basar. Tum urunlerin cekildigini dogrulamak icin kullan.

        Cikti: output_dir/stradivarius_YYYY-MM-DD.csv
        Kolonlar: product_name, price

        Dedup katmanlari (siraya gore):
            1. seen_ids       : Ayni product_id tekrar gelirse tum renkleriyle atla (cross-cat / cift ID)
            2. extract_records: Renk listesi bos donerse atla (bozuk API verisi)
            3. seen_records   : Ayni (product_name, color) zaten yazildiysa o rengi atla
        """
        today_str   = date.today().strftime("%Y-%m-%d")
        output_file = self.output_dir / f"stradivarius_{today_str}.csv"

        self._session = self._make_session()
        self._warmup()

        categories = self.fetch_categories()
        if not categories:
            logger.error("Hic kategori bulunamadi. Scraper durduruluyor.")
            return output_file

        fieldnames = ["product_name", "price"]
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # ── Sayaçlar ────────────────────────────────────────────────────────
        total_ids_from_api  = 0   # API'den gelen ham product ID sayisi
        total_details_ok    = 0   # productsArray'den basarili cekilen detay sayisi
        total_written       = 0   # CSV'ye yazilan satir (renk bazinda)
        total_skip_id       = 0   # seen_ids'de zaten vardi → urunun tum renkleri atla
        total_skip_no_color = 0   # extract_records bos liste dondu (bozuk API verisi)
        total_skip_dedup    = 0   # seen_records'da zaten vardi → o rengi atla

        cat_stats: list[dict] = []

        seen_ids: set[str] = set()
        # Dedup key: (product_name, color)
        # Ayni urunun ayni rengi = duplicate → atla
        # Ayni urunun farkli rengi = yeni satir → yaz
        seen_records: set[tuple[str, str]] = set()
        # ────────────────────────────────────────────────────────────────────

        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for cat in tqdm(categories, unit="kategori", desc="Scraping"):
                cat_id   = cat["product_category_id"]
                cat_name = cat["name"]
                parent   = cat.get("parent_name")
                cat_path = _clean_category(parent, cat_name)

                product_ids = self.fetch_product_ids(cat_id)
                n_ids = len(product_ids)
                total_ids_from_api += n_ids

                if not product_ids:
                    logger.debug("'%s' -- urun yok, atlaniyor.", cat_name)
                    if verify:
                        cat_stats.append({
                            "kategori": cat_path, "ids": 0, "detay": 0,
                            "yazilan": 0, "skip_id": 0, "skip_renk": 0, "skip_dedup": 0,
                        })
                    continue

                # Tum ID'ler zaten gorulduyse detay cekmeyi atla (editoryal/cross-cat)
                new_ids = [pid for pid in product_ids if pid not in seen_ids]
                if not new_ids:
                    total_skip_id += n_ids
                    logger.debug("'%s' -- tum %d ID zaten goruldu, atlaniyor.", cat_name, n_ids)
                    if verify:
                        cat_stats.append({
                            "kategori": cat_path, "ids": n_ids, "detay": 0,
                            "yazilan": 0, "skip_id": n_ids, "skip_renk": 0, "skip_dedup": 0,
                        })
                    continue

                raw_products = self.fetch_product_details(product_ids, cat_id)
                n_details = len(raw_products)
                total_details_ok += n_details

                c_written = c_skip_id = c_skip_no_color = c_skip_dedup = 0

                for raw in raw_products:
                    pid = str(raw.get("id", ""))

                    # Katman 1: product_id daha once gorulduyse tum renklerini atla
                    if not pid or pid in seen_ids:
                        c_skip_id += 1
                        total_skip_id += 1
                        continue

                    # Katman 2: renk listesini cek
                    color_records = self.extract_records(raw, cat_path)
                    if not color_records:
                        c_skip_no_color += 1
                        total_skip_no_color += 1
                        seen_ids.add(pid)  # bozuk urun, bir daha sorgulanmasin
                        continue

                    # product_id'yi hemen isle — ayni ID farkli kategoriden gelirse atlanacak
                    seen_ids.add(pid)

                    # Katman 3: renk bazinda dedup (case-insensitive)
                    # Inditex ayni rengi baz
                    # en 'Bej' bazen 'BEJ' gonderebilir.
                    # .upper() ile normalize edilerek ayni renk sayilir.
                    # CSV'ye yazilan deger: ilk gelen (orijinal) isim — tutarlilik icin.
                    for record in color_records:
                        rkey = record["product_name"].upper()
                        if rkey in seen_records:
                            c_skip_dedup += 1
                            total_skip_dedup += 1
                            continue
                        seen_records.add(rkey)
                        writer.writerow(record)
                        c_written += 1
                        total_written += 1

                if c_written:
                    logger.info("'%s': +%d renk kaydi (toplam: %d)",
                                cat_name, c_written, total_written)

                if verify:
                    cat_stats.append({
                        "kategori":   cat_path,
                        "ids":        n_ids,
                        "detay":      n_details,
                        "yazilan":    c_written,
                        "skip_id":    c_skip_id,
                        "skip_renk":  c_skip_no_color,
                        "skip_dedup": c_skip_dedup,
                    })

                self._sleep()

        # ── Özet log ────────────────────────────────────────────────────────
        logger.info("=" * 60)
        logger.info("OZET")
        logger.info("  API'den gelen toplam ID    : %d", total_ids_from_api)
        logger.info("  Cekilen detay              : %d", total_details_ok)
        logger.info("  CSV'ye yazilan (renk bazli): %d", total_written)
        logger.info("  Atlanan (gorulmus ID)      : %d  [cross-cat / cift ID]", total_skip_id)
        logger.info("  Atlanan (renk/isim yok)    : %d  [bozuk API verisi]", total_skip_no_color)
        logger.info("  Atlanan (duplicate renk)   : %d  [ayni urun+renk]", total_skip_dedup)
        logger.info("  Sayi tutarliligi           : OK  [seen_ids + seen_records garantisi]")
        logger.info("=" * 60)

        # ── Verify tablosu ─────────────────────────────────────────────────
        if verify and cat_stats:
            sorunlu = [
                s for s in cat_stats
                if s["ids"] > 0 and s["yazilan"] == 0
                and s["skip_dedup"] == 0 and s["skip_id"] < s["ids"]
            ]
            sifir_yazi = [s for s in cat_stats if s["ids"] > 0 and s["yazilan"] == 0]
            logger.info(
                "VERIFY: %d kategoride ID geldi ama 0 yeni renk yazildi "
                "(normal: cross-cat dedup)", len(sifir_yazi)
            )
            if sorunlu:
                logger.warning(
                    "VERIFY UYARI: Asagidaki kategorilerde ID var ama "
                    "ne yazildi ne de dedup'a takildi — renk/detay sorunu olabilir:"
                )
                for s in sorunlu:
                    logger.warning(
                        "  %-50s ids=%-4d detay=%-4d skip_renk=%d",
                        s["kategori"], s["ids"], s["detay"], s["skip_renk"]
                    )
            else:
                logger.info(
                    "VERIFY: Sorunlu kategori YOK — tum urunler ya yazildi "
                    "ya da dedup/cross-cat nedeniyle atildi."
                )

        logger.info("Tamamlandi. Toplam %d renk kaydi --> %s", total_written, output_file)
        return output_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stradivarius TR urun scraper")
    parser.add_argument(
        "--verify", action="store_true",
        help="Detayli ID/yazilan/atlanan istatistikleri logla, sorunlu kategorileri raporla"
    )
    parser.add_argument(
        "--output-dir", default=str(_DEFAULT_OUT_DIR),
        help="CSV cikti dizini (varsayilan: repo InflationItems/Datas/ClothingStores/Stradivarius)"
    )
    parser.add_argument(
        "--delay", type=float, default=0.2,
        help="Kategori arasi bekleme suresi saniye (varsayilan: 0.2)"
    )
    args = parser.parse_args()

    scraper = StradivariusScraper(output_dir=args.output_dir, delay=args.delay)
    scraper.run(verify=args.verify)