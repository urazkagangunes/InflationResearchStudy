"""
run_all.py
----------
Tüm scraper'ları, ardından tüm inflation hesaplama scriptlerini sırayla çalıştırır.
Her script ayrı bir subprocess olarak çalışır; hata olursa loglanır ve devam edilir.

Kullanım:
    python run_all.py
"""

import csv
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# ── Scraper'lar (sırayla çalışır) ────────────────────────────────────────────
SCRAPERS = [
    REPO_ROOT / "InflationItems/Codes/HousesRent/Malatya_Elazig_Tunceli/sahibinden_scraper.py",  # ilk sırada — Chrome + Cloudflare manual geçiş gerekir
    REPO_ROOT / "InflationItems/Codes/Markets/Marketzade/marketzade_scraper.py",
    REPO_ROOT / "InflationItems/Codes/Cosmetics/Dermomarket/dermomarket_scraper.py",
    REPO_ROOT / "InflationItems/Codes/HomeGoods/EnglishHome/englishhome_scraper.py",
    REPO_ROOT / "InflationItems/Codes/ConstructionSuppliesMarkets/Hausmart/hausmart_scraper.py",
    REPO_ROOT / "InflationItems/Codes/TechnologicalProducts/Koçtaş/koctas_scraper.py",
    REPO_ROOT / "InflationItems/Codes/ClothingStores/Stradivarius/StradivariusScraper.py",
    REPO_ROOT / "InflationItems/Codes/09_Recreation/Kitapyurdu/kitapyurdu_scraper.py",
]

# ── Inflation scriptleri (sırayla çalışır) ───────────────────────────────────
INFLATION_SCRIPTS = [
    REPO_ROOT / "Inflations/Codes/Markets/Marketzade/marketzade_inflation.py",
    REPO_ROOT / "Inflations/Codes/Cosmetics/Dermomarket/dermomarket_inflation.py",
    REPO_ROOT / "Inflations/Codes/HomeGoods/EnglishHome/englishhome_inflation.py",
    REPO_ROOT / "Inflations/Codes/ConstructionSuppliesMarkets/Hausmart/hausmart_inflation.py",
    REPO_ROOT / "Inflations/Codes/TechnologicalProducts/Koçtaş/koctas_inflation.py",
    REPO_ROOT / "Inflations/Codes/ClothingStores/Stradivarius/stradivarius_inflation.py",
    REPO_ROOT / "Inflations/Codes/HousesRent/Malatya_Elazig_Tunceli/sahibinden_inflation.py",
]


def run_script(script_path: Path) -> tuple[bool, float]:
    """
    Verilen scripti subprocess olarak çalıştırır.
    (success, elapsed_seconds) döner.
    """
    label = script_path.relative_to(REPO_ROOT)
    print(f"\n{'─' * 60}")
    print(f"▶  {label}")
    print(f"{'─' * 60}")

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(script_path.parent),
        )
        elapsed = time.time() - start
        if result.returncode == 0:
            print(f"✓  Tamamlandı  ({elapsed:.1f}s)")
            return True, elapsed
        else:
            print(f"✗  Hata — return code {result.returncode}  ({elapsed:.1f}s)")
            return False, elapsed
    except Exception as exc:
        elapsed = time.time() - start
        print(f"✗  Exception: {exc}  ({elapsed:.1f}s)")
        return False, elapsed


def run_group(scripts: list[Path], group_label: str) -> list[tuple[Path, bool, float]]:
    """Bir grup scripti sırayla çalıştırır, sonuçları döner."""
    print(f"\n{'═' * 60}")
    print(f"  {group_label}")
    print(f"{'═' * 60}")
    results = []
    for script in scripts:
        success, elapsed = run_script(script)
        results.append((script, success, elapsed))
    return results


def print_summary(scraper_results: list, inflation_results: list) -> None:
    """Başarılı/başarısız özetini yazdırır."""
    all_results = scraper_results + inflation_results
    ok  = [(p, e) for p, s, e in all_results if s]
    err = [(p, e) for p, s, e in all_results if not s]

    print(f"\n{'═' * 60}")
    print(f"  ÖZET  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═' * 60}")
    print(f"  Toplam  : {len(all_results)}")
    print(f"  Başarılı: {len(ok)}")
    print(f"  Hatalı  : {len(err)}")

    if ok:
        print("\n  ✓ Başarılı:")
        for path, elapsed in ok:
            print(f"      {path.relative_to(REPO_ROOT)}  ({elapsed:.1f}s)")

    if err:
        print("\n  ✗ Hatalı:")
        for path, elapsed in err:
            print(f"      {path.relative_to(REPO_ROOT)}  ({elapsed:.1f}s)")

    print(f"\n  Toplam süre: {sum(e for _, _, e in all_results):.1f}s")
    print(f"{'═' * 60}\n")


## ── Bugünün veri/enflasyon dosyalarını eşleştirme ───────────────────────────
# Her scraper için: (mağaza adı, data glob pattern, inflation summary path, şehir prefix (opsiyonel))
TODAY_DOT = datetime.now().strftime("%Y.%m.%d")    # 2026.05.24
TODAY_DASH = datetime.now().strftime("%Y-%m-%d")   # 2026-05-24

STORE_MAP = [
    ("Sahibinden (Malatya)",  REPO_ROOT / f"InflationItems/Datas/HousesRent/Malatya_Elazig_Tunceli/Malatya/malatya_rentals_{TODAY_DOT}.csv",
     REPO_ROOT / "Inflations/Datas/HousesRent/Malatya_Elazig_Tunceli/sahibinden_inflation_summary.csv", "malatya"),
    ("Sahibinden (Elazig)",   REPO_ROOT / f"InflationItems/Datas/HousesRent/Malatya_Elazig_Tunceli/Elazig/elazig_rentals_{TODAY_DOT}.csv",
     REPO_ROOT / "Inflations/Datas/HousesRent/Malatya_Elazig_Tunceli/sahibinden_inflation_summary.csv", "elazig"),
    ("Sahibinden (Tunceli)",  REPO_ROOT / f"InflationItems/Datas/HousesRent/Malatya_Elazig_Tunceli/Tunceli/tunceli_rentals_{TODAY_DOT}.csv",
     REPO_ROOT / "Inflations/Datas/HousesRent/Malatya_Elazig_Tunceli/sahibinden_inflation_summary.csv", "tunceli"),
    ("Marketzade",            REPO_ROOT / f"InflationItems/Datas/Markets/Marketzade/{TODAY_DASH}.csv",
     REPO_ROOT / "Inflations/Datas/Markets/Marketzade/marketzade_inflation_summary.csv", None),
    ("Dermomarket",           REPO_ROOT / f"InflationItems/Datas/Cosmetics/Dermomarket/dermomarket_{TODAY_DASH}.csv",
     REPO_ROOT / "Inflations/Datas/Cosmetics/Dermomarket/dermomarket_inflation_summary.csv", None),
    ("EnglishHome",           REPO_ROOT / f"InflationItems/Datas/HomeGoods/EnglishHome/englishhome_{TODAY_DASH}.csv",
     REPO_ROOT / "Inflations/Datas/HomeGoods/EnglishHome/englishhome_inflation_summary.csv", None),
    ("Hausmart",              REPO_ROOT / f"InflationItems/Datas/ConstructionSuppliesMarkets/Hausmart/hausmart_{TODAY_DASH}.csv",
     REPO_ROOT / "Inflations/Datas/ConstructionSuppliesMarkets/Hausmart/hausmart_inflation_summary.csv", None),
    ("Koctas",                REPO_ROOT / f"InflationItems/Datas/TechnologicalProducts/Koçtaş/koctas_{TODAY_DOT}.csv",
     REPO_ROOT / "Inflations/Datas/TechnologicalProducts/Koçtaş/koctas_inflation_summary.csv", None),
    ("Stradivarius",          REPO_ROOT / f"InflationItems/Datas/ClothingStores/Stradivarius/stradivarius_{TODAY_DASH}.csv",
     REPO_ROOT / "Inflations/Datas/ClothingStores/Stradivarius/stradivarius_inflation_summary.csv", None),
]


def _count_csv_rows(path: Path) -> int | None:
    """CSV dosyasındaki veri satırı sayısını döner (header hariç)."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f) - 1  # header hariç
    except Exception:
        return None


def _get_inflation_today(summary_path: Path, city_prefix: str | None) -> dict | None:
    """
    Inflation summary CSV'den bugünün satırını okur.
    city_prefix varsa (sahibinden) o şehrin sütunlarını, yoksa genel sütunları döner.
    """
    if not summary_path.exists():
        return None
    try:
        with open(summary_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if not rows:
            return None
        last_row = rows[-1]
        tarih_val = last_row.get("tarih", "")
        if tarih_val != TODAY_DASH and tarih_val != TODAY_DOT:
            return None
        if city_prefix:
            return {
                "1d": last_row.get(f"{city_prefix}_tuik_weighted_1d", ""),
                "7d": last_row.get(f"{city_prefix}_tuik_weighted_7d", ""),
                "15d": last_row.get(f"{city_prefix}_tuik_weighted_15d", ""),
                "30d": last_row.get(f"{city_prefix}_tuik_weighted_30d", ""),
            }
        else:
            return {
                "1d": last_row.get("tuik_weighted_1d", ""),
                "7d": last_row.get("tuik_weighted_7d", ""),
                "15d": last_row.get("tuik_weighted_15d", ""),
                "30d": last_row.get("tuik_weighted_30d", ""),
            }
    except Exception:
        return None


def _fmt_pct(val: str) -> str:
    """Yuzde degerini formatlar."""
    if not val or val == "":
        return "  --  "
    try:
        num = float(val)
        return f"{num:+.2f}%"
    except (ValueError, TypeError):
        return "  --  "


def print_daily_report() -> None:
    """Gunluk veri + enflasyon ozet tablosu."""
    print(f"\n{'#' * 60}")
    print(f"  GUNLUK RAPOR  --  {TODAY_DASH}")
    print(f"{'#' * 60}")

    # Urun/ilan sayilari
    print(f"\n  {'Magaza':<25} {'Urun/Ilan':>10}")
    print(f"  {'-' * 25} {'-' * 10}")
    total_items = 0
    for store_name, data_path, _, _ in STORE_MAP:
        count = _count_csv_rows(data_path)
        if count is not None:
            print(f"  {store_name:<25} {count:>10,}")
            total_items += count
        else:
            print(f"  {store_name:<25} {'YOK':>10}")
    print(f"  {'-' * 25} {'-' * 10}")
    print(f"  {'TOPLAM':<25} {total_items:>10,}")

    # Enflasyon tablosu (TUIK agirlikli)
    print(f"\n  {'Magaza':<25} {'1g':>8} {'7g':>8} {'15g':>8} {'30g':>8}")
    print(f"  {'-' * 25} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 8}")
    for store_name, _, summary_path, city_prefix in STORE_MAP:
        inf = _get_inflation_today(summary_path, city_prefix)
        if inf:
            print(f"  {store_name:<25} {_fmt_pct(inf['1d']):>8} {_fmt_pct(inf['7d']):>8} {_fmt_pct(inf['15d']):>8} {_fmt_pct(inf['30d']):>8}")
        else:
            print(f"  {store_name:<25} {'--':>8} {'--':>8} {'--':>8} {'--':>8}")

    print(f"{'#' * 60}\n")


def main():
    print(f"{'═' * 60}")
    print(f"  run_all.py  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Repo: {REPO_ROOT}")
    print(f"{'═' * 60}")

    scraper_results   = run_group(SCRAPERS,          "SCRAPERS")
    inflation_results = run_group(INFLATION_SCRIPTS, "INFLATION SCRIPTS")

    print_summary(scraper_results, inflation_results)
    print_daily_report()


if __name__ == "__main__":
    main()
