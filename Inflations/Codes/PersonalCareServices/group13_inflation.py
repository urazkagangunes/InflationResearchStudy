"""
group13_inflation.py — Unified TÜİK Group 13 CPI Inflation Calculator

Calculates inflation for TÜİK COICOP Group 13:
"Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler"
(Personal care, social protection and miscellaneous goods and services — Basket Weight: 4.4935%)

Sub-categories covered and officially weighted:
  1311/1312: Personal care products & appliances (14 Cosmetics retailers) [Weight: 1.2867%]
  1313:      Hairdresser & personal grooming salons (Kolay Randevu, Chambers) [Weight: 0.5853%]
  1321:      Jewellery & watches (Gold market, Saat & Saat) [Weight: 0.4489%]
  1330:      Social protection & daycare services (Private nurseries) [Weight: 0.3517%]
  1390:      Other services (Notary public, Legal/Attorneys, Auto expertise) [Weight: 0.7737%]

Methodology adheres strictly to turkey_inflation.py:
  1. Stage 1 dedup  – duplicate rows within a store are averaged.
  2. Matching       – current vs baseline snapshot matching on (canonical_key, sub_category).
  3. Outlier filter – price changes > 80% excluded.
  4. Stage 2 dedup  – cross-store averaging per product.
  5. Metrics        – Dutot (basic_index), Carli (avg_inflation), Median,
                      and TÜİK official sub-weight weighted CPI.

Usage:
  python group13_inflation.py
  python group13_inflation.py --date 2026-10-06
  python group13_inflation.py --date 2026-10-06 --compare 2026-10-05
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

# Path setup
_THIS_DIR = Path(__file__).resolve().parent
_CODES_DIR = _THIS_DIR.parent
_PROJECT_ROOT = _CODES_DIR.parent.parent

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Group13Inflation")

# Official TÜİK sub-category basket weights within Group 13
TUIK_SUB_WEIGHTS = {
    "1312": ("Kişisel Bakım Ürünleri (Cosmetics)", 1.2867),
    "1313": ("Kuaför ve Berber Hizmetleri (Hairdresser)", 0.5853),
    "1321": ("Mücevherat ve Kol Saatleri (Jewelry & Watches)", 0.4489),
    "1330": ("Sosyal Koruma ve Kreş (Daycare & Nursery)", 0.3517),
    "1390": ("Diğer Hizmetler - Noter, Hukuk, Ekspertiz (Services)", 0.7737),
}

SECTOR_SOURCES = [
    ("Cosmetics", _PROJECT_ROOT / "InflationItems/Datas/Cosmetics", "1312"),
    ("Hairdresser", _PROJECT_ROOT / "InflationItems/Datas/Hairdresser", "1313"),
    ("Jewelry", _PROJECT_ROOT / "InflationItems/Datas/Jewelry", "1321"),
    ("Daycare", _PROJECT_ROOT / "InflationItems/Datas/Daycare", "1330"),
    ("Services", _PROJECT_ROOT / "InflationItems/Datas/Services", "1390"),
]

OUT_DIR = _PROJECT_ROOT / "Inflations/Datas/Group13"

_NAME_ALIASES = ("product_name", "product name", "isim", "urun_adi", "name", "title")
_PRICE_ALIASES = ("price", "product cost", "fiyat", "normal_price")


def _norm(text: str) -> str:
    """Normalize string for product matching."""
    s = text.lower().strip()
    s = s.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _parse_price(val: any) -> float | None:
    """Parses numeric price from various string formats."""
    if val is None:
        return None
    s = str(val).strip().replace("₺", "").replace("TL", "").replace("TRY", "").strip()
    if not s or s.startswith("-"):
        return None
    # Turkish format 1.234,56
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        p = float(s)
        return p if p > 0 else None
    except ValueError:
        return None


def _read_csv_file(fpath: Path, store: str, subcat: str) -> list[dict]:
    """Reads a CSV into list of standardized dicts."""
    rows = []
    try:
        with fpath.open(encoding="utf-8-sig", errors="ignore") as fh:
            reader = csv.reader(fh)
            first = next(reader, None)
            if not first:
                return []

            first_lower = [c.strip().strip('"').lower() for c in first]
            has_header = bool(set(first_lower) & set(_NAME_ALIASES)) and bool(set(first_lower) & set(_PRICE_ALIASES))

            if has_header:
                name_idx = next(i for i, a in enumerate(first_lower) if a in _NAME_ALIASES)
                price_idx = next(i for i, a in enumerate(first_lower) if a in _PRICE_ALIASES)
            else:
                name_idx = 0
                price_idx = 1
                # Treat first row as data
                if len(first) >= 2:
                    p = _parse_price(first[price_idx])
                    if p:
                        raw_name = first[name_idx].strip()
                        c_key = _norm(raw_name)
                        if c_key:
                            rows.append({"product_name": raw_name, "canonical_key": c_key, "price": p, "store": store, "subcat": subcat})

            for line in reader:
                if len(line) <= max(name_idx, price_idx):
                    continue
                p = _parse_price(line[price_idx])
                if not p:
                    continue
                raw_name = line[name_idx].strip()
                c_key = _norm(raw_name)
                if c_key:
                    rows.append({"product_name": raw_name, "canonical_key": c_key, "price": p, "store": store, "subcat": subcat})
    except Exception as exc:
        logger.warning("[%s] Error reading %s: %s", store, fpath.name, exc)
    return rows


def load_all_group13_data(date_str: str) -> tuple[dict[tuple[str, str], float], dict[str, int]]:
    """
    Loads all Group 13 datasets for date_str.
    Returns:
      - dict mapping (canonical_key, subcat) -> averaged price
      - dict counts per subcat
    """
    raw_by_store: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    name_lookup: dict[tuple[str, str], str] = {}
    counts_by_subcat = {k: 0 for k in TUIK_SUB_WEIGHTS}

    for sector_name, root_dir, subcat in SECTOR_SOURCES:
        if not root_dir.exists():
            continue

        subdirs = [p for p in root_dir.iterdir() if p.is_dir()]
        target_dirs = subdirs if subdirs else [root_dir]

        for sdir in target_dirs:
            store_name = sdir.name
            matches = sorted(sdir.glob(f"*{date_str}*.csv"))
            if not matches:
                continue
            csv_path = matches[0]
            items = _read_csv_file(csv_path, store_name, subcat)
            counts_by_subcat[subcat] += len(items)

            for item in items:
                ck = item["canonical_key"]
                sc = item["subcat"]
                st = item["store"]
                raw_by_store[(ck, sc, st)].append(item["price"])
                if (ck, sc) not in name_lookup:
                    name_lookup[(ck, sc)] = item["product_name"]

    if not raw_by_store:
        return {}, counts_by_subcat

    # Stage 1: within-store mean
    store_means: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (ck, sc, st), prices in raw_by_store.items():
        store_means[(ck, sc)].append(sum(prices) / len(prices))

    # Stage 2: cross-store mean
    final_prices: dict[tuple[str, str], tuple[str, float]] = {}
    for (ck, sc), s_means in store_means.items():
        avg_price = sum(s_means) / len(s_means)
        final_prices[(ck, sc)] = (name_lookup.get((ck, sc), ck), avg_price)

    return final_prices, counts_by_subcat


def calculate_group13_inflation(target_date: str | None = None,
                                compare_date: str | None = None) -> None:
    """Calculates Group 13 inflation metrics."""
    base_date = datetime.strptime(target_date, "%Y-%m-%d") if target_date else datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    logger.info("Loading Group 13 data for current date: %s", today_str)
    curr_data, counts_curr = load_all_group13_data(today_str)
    if not curr_data:
        logger.warning("No data found for %s. Aborting.", today_str)
        return

    logger.info("Current snapshot: %d unique products across Group 13.", len(curr_data))
    for sc, count in counts_curr.items():
        logger.info("   Sub-category %s (%s): %d raw items", sc, TUIK_SUB_WEIGHTS[sc][0], count)

    intervals = []
    if compare_date:
        intervals.append((compare_date, f"Custom ({compare_date})"))
    else:
        for days, label in [(1, "1d"), (15, "15d"), (30, "30d")]:
            c_date = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            intervals.append((c_date, label))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows = []

    for comp_str, interval_label in intervals:
        logger.info("Comparing with baseline date: %s (%s)...", comp_str, interval_label)
        past_data, counts_past = load_all_group13_data(comp_str)
        if not past_data:
            logger.info("No data found for baseline date %s — skipping.", comp_str)
            continue

        # Match keys
        matched = []
        for (ck, sc), (name_c, price_c) in curr_data.items():
            if (ck, sc) in past_data:
                _, price_p = past_data[(ck, sc)]
                pct_change = ((price_c - price_p) / price_p) * 100
                if abs(pct_change) <= 80:  # Outlier threshold
                    matched.append({
                        "canonical_key": ck,
                        "subcat": sc,
                        "product_name": name_c,
                        "price_past": price_p,
                        "price_current": price_c,
                        "price_diff": price_c - price_p,
                        "pct_change": pct_change,
                    })

        if not matched:
            logger.warning("No matched products between %s and %s.", today_str, comp_str)
            continue

        # Basic Index (Dutot)
        sum_curr = sum(m["price_current"] for m in matched)
        sum_past = sum(m["price_past"] for m in matched)
        dutot_index = ((sum_curr / sum_past) - 1) * 100 if sum_past > 0 else 0.0

        # Carli Index (Arithmetic Mean of changes)
        carli_index = sum(m["pct_change"] for m in matched) / len(matched)

        # Median Index
        median_index = median([m["pct_change"] for m in matched])

        # TÜİK Sub-category Weighted Laspeyres Index
        subcat_changes: dict[str, list[float]] = defaultdict(list)
        for m in matched:
            subcat_changes[m["subcat"]].append(m["pct_change"])

        weighted_sum = 0.0
        covered_weight = 0.0
        for sc, (desc, w) in TUIK_SUB_WEIGHTS.items():
            if sc in subcat_changes and subcat_changes[sc]:
                sc_mean = sum(subcat_changes[sc]) / len(subcat_changes[sc])
                weighted_sum += sc_mean * w
                covered_weight += w

        tuik_weighted_cpi = (weighted_sum / covered_weight) if covered_weight > 0 else carli_index

        logger.info("--------------------------------------------------")
        logger.info("GROUP 13 INFLATION RESULTS [%s vs %s] (%s):", today_str, comp_str, interval_label)
        logger.info("  Matched Items Count  : %d", len(matched))
        logger.info("  Dutot (Basic) Index  : %+.2f%%", dutot_index)
        logger.info("  Carli (Avg) Index    : %+.2f%%", carli_index)
        logger.info("  Median Change        : %+.2f%%", median_index)
        logger.info("  TÜİK Weighted CPI    : %+.2f%% (Normalized basket weight: %.2f%%)",
                    tuik_weighted_cpi, covered_weight)
        logger.info("--------------------------------------------------")

        summary_rows.append({
            "target_date": today_str,
            "compare_date": comp_str,
            "interval": interval_label,
            "matched_items": len(matched),
            "dutot_index": round(dutot_index, 4),
            "carli_index": round(carli_index, 4),
            "median_index": round(median_index, 4),
            "tuik_weighted_cpi": round(tuik_weighted_cpi, 4),
            "basket_weight_covered": round(covered_weight, 4),
        })

        # Save product-level matched details
        detail_path = OUT_DIR / f"group13_matched_{today_str}_vs_{comp_str}.csv"
        with open(detail_path, "w", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "product_name", "subcat", "price_past", "price_current", "price_diff", "pct_change"
            ])
            writer.writeheader()
            for m in matched:
                writer.writerow({
                    "product_name": m["product_name"],
                    "subcat": m["subcat"],
                    "price_past": round(m["price_past"], 2),
                    "price_current": round(m["price_current"], 2),
                    "price_diff": round(m["price_diff"], 2),
                    "pct_change": round(m["pct_change"], 4),
                })

    if summary_rows:
        summary_path = OUT_DIR / "group13_inflation_summary.csv"
        existing_rows = []
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                existing_rows = list(reader)

        # Merge and upsert
        keys = {(r["target_date"], r["compare_date"]) for r in summary_rows}
        merged = [r for r in existing_rows if (r["target_date"], r["compare_date"]) not in keys]
        merged.extend(summary_rows)

        with open(summary_path, "w", encoding="utf-8") as f:
            fieldnames = [
                "target_date", "compare_date", "interval", "matched_items",
                "dutot_index", "carli_index", "median_index", "tuik_weighted_cpi",
                "basket_weight_covered"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in merged:
                writer.writerow(r)
        logger.info("Saved Group 13 inflation summary to %s", summary_path)


def main():
    parser = argparse.ArgumentParser(description="TÜİK Group 13 CPI Calculator")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--compare", type=str, default=None, help="Compare date YYYY-MM-DD")
    args = parser.parse_args()

    calculate_group13_inflation(args.date, args.compare)


if __name__ == "__main__":
    main()
