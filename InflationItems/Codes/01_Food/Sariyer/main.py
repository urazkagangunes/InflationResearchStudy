"""
main.py — Sarıyer Market Ürün Scraper'ı
=========================================

Kullanım örnekleri:

  # Mevcut tüm kategorileri listele
  python main.py --list-categories

  # Tek bir kategori çek (slug veya ID ile), CSV olarak kaydet
  python main.py --category meyve-sebze --output csv

  # Tüm kategorileri çek; hem CSV hem JSON kaydet; 1 sn bekleme
  python main.py --output both --delay 1.0

  # Kategori başına en fazla 2 sayfa çek (hızlı test)
  python main.py --output both --limit 2

  # Kesilmiş bir çalıştırmaya devam et (checkpoint'ten yükle)
  python main.py --output csv --resume

  # Debug log'u aç
  python main.py --verbose
"""

import argparse
import json
import logging
import os
import sys

import pandas as pd
import requests
from tqdm import tqdm

import config
from category_fetcher import fetch_categories
from product_fetcher import fetch_products_for_category

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Checkpoint yardımcıları ──────────────────────────────────────────────────

def _load_checkpoint() -> dict:
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done": [], "method": {}}   # method: hangi stratejiyle çekildi


def _save_checkpoint(checkpoint: dict) -> None:
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


# ── Çıktı yardımcıları ───────────────────────────────────────────────────────

def _append_products(new_products: list[dict], output_format: str) -> None:
    """
    Her kategori bittikten hemen sonra çağrılır.
    Kesintide veri kaybolmaması için artımlı kayıt yapılır.
    """
    if not new_products:
        return

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    df_new = pd.DataFrame(new_products)
    df_new = df_new[["name", "shown_price"]]
    if output_format in ("csv", "both"):
        write_header = not os.path.exists(config.CSV_OUTPUT_FILE)
        df_new.to_csv(
            config.CSV_OUTPUT_FILE,
            mode="a",
            index=False,
            header=write_header,
            encoding="utf-8-sig",
        )

    if output_format in ("json", "both"):
        existing: list[dict] = []
        if os.path.exists(config.JSON_OUTPUT_FILE):
            try:
                with open(config.JSON_OUTPUT_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = []
        existing.extend(new_products)
        with open(config.JSON_OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)


def _dedup_csv() -> int:
    """CSV'deki yinelenen ürün ID'lerini kaldırır. Nihai satır sayısını döner."""
    if not os.path.exists(config.CSV_OUTPUT_FILE):
        return 0
    df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
    before = len(df)
    df.drop_duplicates(subset=["name"], keep="first", inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(config.CSV_OUTPUT_FILE, index=False, encoding="utf-8-sig")
    removed = before - len(df)
    if removed:
        logger.info("%d yinelenen kayıt silindi. Son satır sayısı: %d", removed, len(df))
    return len(df)


def _dedup_json() -> None:
    """JSON'daki yinelenen ürün ID'lerini kaldırır."""
    if not os.path.exists(config.JSON_OUTPUT_FILE):
        return
    with open(config.JSON_OUTPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    seen: set[str] = set()
    deduped = [
        item for item in data
        if (pid := str(item.get("name", ""))) not in seen and not seen.add(pid)
    ]
    with open(config.JSON_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)


# ── Ana scraping mantığı ─────────────────────────────────────────────────────

def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def run_scraper(args: argparse.Namespace) -> None:
    session = _make_session()

    # 1. Kategorileri çek
    logger.info("Kategori listesi alınıyor…")
    try:
        categories = fetch_categories(session=session)
    except RuntimeError as exc:
        logger.error("Kategoriler alınamadı: %s", exc)
        sys.exit(1)

    if not categories:
        logger.error("Hiçbir kategori bulunamadı. Çıkılıyor.")
        sys.exit(1)

    # 2. Tek kategori filtresi (--category)
    if args.category:
        categories = [
            c for c in categories
            if c["id"] == args.category or c["name"] == args.category
        ]
        if not categories:
            logger.error(
                "'%s' ID/adında kategori bulunamadı. "
                "Mevcut kategoriler için --list-categories kullanın.",
                args.category,
            )
            sys.exit(1)

    # 3. Checkpoint yükle (--resume)
    checkpoint = _load_checkpoint() if args.resume else {"done": [], "method": {}}

    # 4. Taze (resume değil) çalıştırmada eski çıktıları sil
    if not args.resume:
        for fpath in [config.CSV_OUTPUT_FILE, config.JSON_OUTPUT_FILE]:
            if os.path.exists(fpath):
                os.remove(fpath)
                logger.info("Eski dosya silindi: %s", fpath)

    categories_to_scrape = [
        c for c in categories if c["id"] not in checkpoint["done"]
    ]

    if not categories_to_scrape:
        logger.info(
            "Tüm kategoriler zaten çekilmiş. "
            "Sıfırdan başlamak için --resume olmadan çalıştırın."
        )
        return

    total_products = 0

    # Resume: mevcut ürün sayısını say
    if args.resume and os.path.exists(config.CSV_OUTPUT_FILE):
        try:
            existing_df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
            total_products = len(existing_df)
            logger.info(
                "Devam ediliyor: %d mevcut ürün (%s)",
                total_products, config.CSV_OUTPUT_FILE,
            )
        except Exception as exc:
            logger.warning("Mevcut ürün sayısı alınamadı: %s", exc)

    logger.info(
        "%d kategori scrape edilecek…",
        len(categories_to_scrape),
    )

    with tqdm(categories_to_scrape, unit="kategori", desc="Kategoriler") as pbar:
        for cat in pbar:
            pbar.set_postfix_str(cat["name"][:30])

            cat_products = fetch_products_for_category(
                category=cat,
                session=session,
                delay=args.delay,
                page_limit=args.limit,
            )

            # Her kategoriden hemen sonra kaydet — kesintide veri kaybolmaz
            if cat_products:
                _append_products(cat_products, args.output)
                total_products += len(cat_products)

            checkpoint["done"].append(cat["id"])
            _save_checkpoint(checkpoint)

            logger.info(
                "Kategori '%s': +%d ürün (toplam: %d)",
                cat["name"], len(cat_products), total_products,
            )

    # 5. Son yinelenme temizliği
    logger.info("Yinelenme temizleniyor…")
    final_count = _dedup_csv()
    if args.output in ("json", "both"):
        _dedup_json()

    logger.info("✓ Tamamlandı! Toplam benzersiz ürün: %d", final_count)
    logger.info("Çıktı → %s", config.CSV_OUTPUT_FILE)
    if args.output in ("json", "both"):
        logger.info("Çıktı → %s", config.JSON_OUTPUT_FILE)


# ── CLI ──────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sariyermarket-scraper",
        description="Sarıyer Market (sariyermarket.com) ürün verisi çekici.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="Mevcut kategorileri listele ve çık.",
    )
    parser.add_argument(
        "--category",
        metavar="ID_VEYA_ADI",
        default=None,
        help="Sadece bu kategoriyi çek (ör. 'meyve-sebze'). "
             "Belirtilmezse tüm kategoriler çekilir.",
    )
    parser.add_argument(
        "--output",
        choices=["csv", "json", "both"],
        default="both",
        help="Çıktı formatı (varsayılan: both).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=config.REQUEST_DELAY,
        metavar="SANIYE",
        help=f"Sayfa istekleri arası bekleme süresi (varsayılan: {config.REQUEST_DELAY}s).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="SAYFA",
        help="Kategori başına maksimum sayfa sayısı (0 = sınırsız, test için kullanışlı).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Checkpoint dosyasından devam et (tamamlanan kategorileri atla).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Ayrıntılı (DEBUG seviyesi) log'u aktif et.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_categories:
        session = _make_session()
        try:
            categories = fetch_categories(session=session)
        except RuntimeError as exc:
            logger.error(str(exc))
            sys.exit(1)

        print(f"\n{'ID / Slug':<30} {'Ad':<40} {'Ürün Sayısı'}")
        print("-" * 80)
        for cat in categories:
            count = str(cat.get("product_count") or "?")
            parent = f"  └─ [{cat['parent_name']}]" if cat.get("parent_name") else ""
            print(f"{cat['id']:<30} {cat['name']:<40} {count:>6} {parent}")
        print(f"\nToplam: {len(categories)} kategori")
        return

    run_scraper(args)


if __name__ == "__main__":
    main()

