"""
turkey_inflation.py — Turkey-Wide Daily Inflation Calculator

Aggregates scraped retail price data across nine sectors and computes four
inflation metrics for each comparison interval:

  1. basic_index          – Dutot index: (Σp_t / Σp_0 − 1) × 100
                            Ratio of current to past basket sum. Gives larger
                            products (by price) more implicit weight.

  2. avg_inflation        – Carli index: arithmetic mean of per-product price
                            relatives (p_t / p_0 − 1) × 100. Each matched
                            product receives equal weight.

  3. tuik_weighted_products – Two-stage Carli weighted by TÜİK 2026 COICOP
                            basket weights. Stage 1: unweighted mean of product
                            relatives within each TUIK category. Stage 2:
                            weighted average across categories using normalised
                            TÜİK weights (rescaled to sum to 100% over tracked
                            categories only). Excludes rent (group 04).

  4. tuik_weighted_full   – Same as tuik_weighted_products but with rent
                            inflation (group 04) injected when city-level rent
                            data is available for both dates. Weights are
                            renormalised to include group 04.

  5. median_inflation     – Median of per-product relatives. Typically 0% since
                            most products do not reprice between monthly
                            snapshots. Use median_inflation_nonzero instead for
                            the typical repricing magnitude.
                            Also reported per interval:
                              median_inflation_nonzero – median among products
                                that actually repriced (|relative| > 1e-9%)
                              pct_increased / pct_decreased / pct_unchanged –
                                share of products in each direction (sum to 100%)

Sectors and TUIK groups covered:
  Grocery markets      → group 01  (Gıda ve alkolsüz içecekler)
  Clothing stores      → group 03  (Giyim ve ayakkabı)
  Rent / housing       → group 04  (Konut, su, elektrik, gaz) [city-level]
  HomeGoods +
  ConstructionSupplies → group 05  (Mobilya, mefruşat ve ev ekipmanları)
  Health               → group 06  (Sağlık) [monthly snapshots]
  Tech products        → group 08  (Bilgi ve iletişim)
  Travel/Tourism +
  Restaurants          → group 11  (Lokantalar ve konaklama hizmetleri)
  Cosmetics            → group 13  (Kişisel bakım)

Deduplication (two-stage):
  Stage 1 — within store: duplicate rows for the same product in one store's
    CSV are collapsed to a single row by averaging prices.
  Stage 2 — cross-store, then cross-sector: matched products are first averaged
    across stores (equal store weight), then averaged across sectors that share
    the same TUIK category (e.g. HomeGoods and ConstructionSupplies both map to
    group 05). This prevents the same physical product from being double-counted
    in the basket or the weighted index.
  Matching key: normalised product name (Turkish diacritics stripped,
    lowercased, whitespace collapsed) × TUIK category × store × sector.

Outlier filtering:
  Product-store pairs whose price changed by more than ±_OUTLIER_THRESHOLD %
  (default 80%) between snapshots are treated as scraping artefacts and excluded
  from all metrics. Both the relative and the underlying prices are nullified for
  those rows so they do not bias the Dutot index either.

Rent treatment:
  Rent is loaded separately from city-level listing files (HousesRent/).  The
  inflation rate is computed as the Carli index across cities: arithmetic mean of
  (mean_current_rent_city / mean_past_rent_city − 1) × 100 over all cities
  present in both snapshots. This city-level relative is injected into
  tuik_weighted_full as group 04; it does not enter basic_index, avg_inflation,
  or tuik_weighted_products, which are product-level metrics only.

Output files (Inflations/Datas/Final_Reports/):
  turkey_inflation_{YYYY-MM-DD}.csv  — one row per (canonical_key, tuik_category,
                                       sector) with product_key, store, and
                                       relative_{label} columns per interval

  turkey_inflation_summary.csv       — one row per (date, compare_date) with:
                                         basket_coverage_pct      – product-only
                                           share of TÜİK basket tracked
                                         basket_coverage_full_pct – includes
                                           group 04 when rent data is present
                                         n_products_matched_{label} – products
                                           that matched across both dates and
                                           entered the inflation calculation
                                         all five metrics per interval, per-
                                           category breakdowns, and store/product
                                           count metadata

Usage:
    python turkey_inflation.py                    # today, 15d / 30d intervals
    python turkey_inflation.py --date 2026-05-01  # specific target date
    python turkey_inflation.py --date 2026-05-01 --compare 2026-04-01
"""

import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent          # InflationResearchStudy/

sys.path.insert(0, str(_THIS_DIR))
from tuik_config import normalised_weights, TUIK_WEIGHTS

_DATA_ROOT = _PROJECT_ROOT / "InflationItems" / "Datas"
_OUT_DIR = _PROJECT_ROOT / "Inflations" / "Datas" / "Final_Reports"

logger = logging.getLogger(__name__)

# Products whose price changed by more than this absolute % between snapshots are treated
# as scraping artefacts (e.g. a unit-price recorded at the kg-price scale).
# Documented at module level for reproducibility; run sensitivity analyses at ±20 pp.
_OUTLIER_THRESHOLD = 80.0

# Products whose price relative falls within ±_ZERO_CHANGE_TOL % are classified as
# "unchanged". Floating-point arithmetic can produce non-zero relatives for products
# whose price literally did not change (e.g. 0.499 → 0.499 via two parse paths);
# this tolerance prevents those from inflating pct_increased / pct_decreased.
_ZERO_CHANGE_TOL = 1e-9

# ── Turkish character normalisation ───────────────────────────────────────────
_TR_MAP = str.maketrans("ıİğĞşŞçÇöÖüÜ", "iIgGsScCoOuU")


def _norm(s: str) -> str:
    """Normalise a product name for cross-store deduplication."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.translate(_TR_MAP).lower().strip())


# ── Price parsing ─────────────────────────────────────────────────────────────

def _parse_price(x) -> float | None:
    """
    Parse a price from any format observed in the codebase:
      - Pure numeric (float / int)
      - Turkish: "1.234,56" or "1.250.000" or "149,50"
      - Lira prefix/suffix: "₺149,50"  /  "34,99 ₺"  /  "2.475,00TL"
      - Complex prefix: "Başlangıç:  129.999,00 ₺"
      - Single dot with 3 trailing digits: "50.499" → 50499 (Turkish thousands)
    """
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return None if pd.isna(x) else float(x)

    s = str(x).strip()
    if not s:
        return None

    # Strip lira symbol, TL / TRY suffix, leading labels like "Başlangıç:"
    s = re.sub(r"₺|\bTL\b|\bTRY\b", "", s, flags=re.IGNORECASE).strip()
    # Strip trailing non-numeric suffix (e.g. "/Kg")
    s = re.sub(r"[^\d.,]+$", "", s).strip()
    # If complex prefix remains, extract the longest numeric token (= the price)
    if not re.match(r"^[\d.,]+$", s):
        m = re.findall(r"\d[\d,.]*\d|\d", s)
        if not m:
            return None
        s = max(m, key=len)

    # Normalise separators
    if "." in s and "," in s:
        if s.index(".") < s.index(","):
            # Turkish: "1.234,56"
            s = s.replace(".", "").replace(",", ".")
        else:
            # English thousands: "1,234.56"
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        # Multiple dots → Turkish thousands "1.250.000"
        s = s.replace(".", "")
    elif re.match(r"^\d+\.\d{3}$", s):
        # "1.234" or "50.499" → Turkish thousands separator → 1234 / 50499.
        # "0.499" is unambiguously decimal (0.499 TL); leave it intact.
        if s.split(".")[0] != "0":
            s = s.replace(".", "")

    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


# ── File header validation ────────────────────────────────────────────────────

_SKIP_SUBDIRS = {"InflationData", "output", "reports", "archive"}
_STANDARD_COLS = ["canonical_key", "product_key", "price", "store", "sector", "tuik_category"]


_NAME_ALIASES  = {"product_name", "product name", "isim"}
_PRICE_ALIASES = {"price", "product cost", "fiyat"}


def _has_standard_header(fpath: Path) -> bool:
    try:
        with fpath.open(encoding="utf-8", errors="ignore") as fh:
            first = fh.readline().strip().lstrip("﻿")
        cols = {c.strip().lower() for c in first.split(",")}
        return bool(cols & _NAME_ALIASES) and bool(cols & _PRICE_ALIASES)
    except Exception:
        return False


def _find_date_csv(store_dir: Path, date_token: str) -> Path | None:
    candidates = [
        f for f in sorted(store_dir.rglob(f"*{date_token}*.csv"))
        if not any(p in _SKIP_SUBDIRS for p in f.relative_to(store_dir).parts[:-1])
        and _has_standard_header(f)
    ]
    if not candidates:
        return None
    if len(candidates) > 1:
        logger.warning(
            "%s: %d CSVs match date token '%s' — using %s (ignoring: %s)",
            store_dir.name, len(candidates), date_token,
            candidates[0].name, ", ".join(f.name for f in candidates[1:]),
        )
    return candidates[0]


def _load_store_csv(fpath: Path, store: str, sector: str, tuik_code: str) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(fpath, dtype=str, on_bad_lines="skip")
        df.columns = [c.lstrip("﻿").strip() for c in df.columns]
        col_lower = {c.lower(): c for c in df.columns}
        col_map = {}
        if "product_name" not in df.columns:
            for alias in ("product name", "isim"):
                if alias in col_lower:
                    col_map[col_lower[alias]] = "product_name"
                    break
        if "price" not in df.columns:
            for alias in ("product cost", "fiyat"):
                if alias in col_lower:
                    col_map[col_lower[alias]] = "price"
                    break
        if col_map:
            df = df.rename(columns=col_map)
        if "product_name" not in df.columns or "price" not in df.columns:
            return None
        out = pd.DataFrame()
        out["product_key"] = df["product_name"].astype(str).str.strip()
        out["canonical_key"] = out["product_key"].apply(_norm)
        # Filter out prices that have a leading minus sign
        out["price"] = df["price"].apply(
            lambda x: _parse_price(x) if (x is None or not str(x).strip().startswith("-")) else None
        )
        out["store"] = store
        out["sector"] = sector
        out["tuik_category"] = tuik_code
        out = out[out["canonical_key"] != ""].dropna(subset=["price"])
        out = out[out["price"] > 0].reset_index(drop=True)
        return out if not out.empty else None
    except Exception as e:
        logger.debug("%s: failed to load %s — %s", store, fpath.name, e)
        return None


# Stores permanently excluded from inflation calculation (volatile/unreliable pricing)
_SKIP_STORES: set[str] = {"EnglishHome"}

# ── Sector-based auto-discovery registry ─────────────────────────────────────

# Maps sector directory name → (tuik_code, sector_label, date_granularity)
# date_granularity: "daily" matches *YYYY-MM-DD*, "monthly" matches *YYYY-MM*
_SECTOR_CONFIG: dict[str, tuple[str, str, str]] = {
    "01_Food":                                ("01", "market",       "daily"),
    "03_Clothing":                            ("03", "clothing",     "daily"),
    "04_Housing":                             ("04", "rent",         "daily"),
    "05_Furnishings/HomeGoods":               ("05", "homegoods",    "daily"),
    "05_Furnishings/ConstructionSuppliesMarkets": ("05", "construction", "daily"),
    "06_Health":                              ("06", "health",       "monthly"),
    "07_Transport/PublicTransportation":      ("07", "transport",    "daily"),
    "07_Transport/motor_bicyle_car":          ("07", "vehicle",      "daily"),
    "08_Communication":                       ("08", "tech",         "daily"),
    "09_Recreation":                          ("09", "recreation",   "daily"),
    "11_Restaurants/TravelTourism":           ("11", "tourism",      "daily"),
    "11_Restaurants/RestaurantMealPricesVenueHallRentalFees": ("11", "restaurant",  "flat_daily"),
    "13_Personal_Care/Cosmetics":             ("13", "cosmetics",    "daily"),
    "13_Personal_Care/Jewelry":               ("13", "jewelry",      "daily"),
    "13_Personal_Care/Hairdresser":           ("13", "hairdresser",  "daily"),
    "13_Personal_Care/Services":              ("13", "services",     "daily"),
    "13_Personal_Care/Daycare":               ("13", "daycare",      "daily"),
}


def _load_sector(
    sector_dir: Path,
    date_str: str,
    tuik_code: str,
    sector_label: str,
    date_granularity: str = "daily",
) -> list[pd.DataFrame]:
    date_token = date_str[:7] if date_granularity == "monthly" else date_str
    frames = []
    for store_dir in sorted(sector_dir.iterdir()):
        if not store_dir.is_dir():
            continue
        if store_dir.name in _SKIP_STORES:
            continue
        fpath = _find_date_csv(store_dir, date_token)
        if fpath is None:
            continue
        df = _load_store_csv(fpath, store_dir.name, sector_label, tuik_code)
        if df is not None and not df.empty:
            frames.append(df)
    return frames


def _load_flat_sector(
    sector_dir: Path,
    date_str: str,
    tuik_code: str,
    sector_label: str,
) -> list[pd.DataFrame]:
    """Load CSVs that sit directly in sector_dir (no store subdirs).

    Each file's stem (without the date suffix) becomes the store name.
    """
    frames = []
    for fpath in sorted(sector_dir.glob(f"*{date_str}*.csv")):
        if not fpath.is_file():
            continue
        if not _has_standard_header(fpath):
            continue
        store_name = fpath.stem.rsplit(f"_{date_str}", 1)[0]
        df = _load_store_csv(fpath, store_name, sector_label, tuik_code)
        if df is not None and not df.empty:
            frames.append(df)
    return frames


# ── Pool loading and deduplication ────────────────────────────────────────────

def _load_all_stores(date_str: str) -> tuple[pd.DataFrame, list[str], int]:
    """
    Load all stores for a given date via sector auto-discovery.

    Returns
    -------
    df          : combined and deduplicated DataFrame
    stores_ok   : list of store names that had data
    n_before    : total product count before deduplication
    """
    frames: list[pd.DataFrame] = []
    for sector_name, (tuik_code, sector_label, date_gran) in _SECTOR_CONFIG.items():
        sector_dir = _DATA_ROOT / sector_name
        if not sector_dir.exists():
            continue
        if date_gran == "flat_daily":
            frames.extend(_load_flat_sector(sector_dir, date_str, tuik_code, sector_label))
        else:
            frames.extend(_load_sector(sector_dir, date_str, tuik_code, sector_label, date_gran))

    if not frames:
        return pd.DataFrame(columns=_STANDARD_COLS), [], 0

    combined = pd.concat(frames, ignore_index=True)
    n_before = len(combined)
    stores_ok = list(combined["store"].unique())

    # Deduplicate within each store (same product appearing twice in one CSV)
    deduped = (
        combined
        .groupby(["store", "canonical_key", "tuik_category", "sector"], as_index=False)
        .agg(
            product_key=("product_key", "first"),
            price=("price", "mean"),
        )
    )
    return deduped, stores_ok, n_before


# ── Rent inflation helper ─────────────────────────────────────────────────────

def _rent_city_prices(date_str: str) -> dict[str, float]:
    rent_root = _DATA_ROOT / "HousesRent"
    city_prices: dict[str, list[float]] = {}
    for fpath in rent_root.rglob(f"*{date_str}*.csv"):
        if fpath.parent == rent_root:  # skip root-level aggregate files
            continue
        if not _has_standard_header(fpath):
            continue
        city_key = fpath.parent.name
        try:
            df = pd.read_csv(fpath, dtype=str, on_bad_lines="skip")
            df.columns = [c.lstrip("﻿").strip() for c in df.columns]
            col_lower = {c.lower(): c for c in df.columns}
            price_col = next(
                (col_lower[a] for a in ("price", "product cost", "fiyat") if a in col_lower),
                None,
            )
            if price_col is None:
                logger.debug("rent file %s has no recognised price column — skipping", fpath.name)
                continue
            prices = df[price_col].apply(_parse_price).dropna()
            prices = prices[prices > 0]
            if not prices.empty:
                city_prices.setdefault(city_key, []).extend(prices.tolist())
        except Exception:
            continue
    return {k: sum(v) / len(v) for k, v in city_prices.items()}


_RENT_MIN_COMMON_CITIES = 3


def _rent_relative(cur_city: dict[str, float], past_str: str) -> float | None:
    """Compare pre-loaded current city prices against past city prices."""
    past_city = _rent_city_prices(past_str)
    common = set(cur_city) & set(past_city)
    if not common:
        return None
    if len(common) < _RENT_MIN_COMMON_CITIES:
        logger.warning(
            "rent_inflation (cur vs %s) based on only %d common city/cities: %s — result may not be representative",
            past_str, len(common), sorted(common),
        )
    city_relatives = [
        (cur_city[c] / past_city[c] - 1) * 100
        for c in common
        if past_city[c] > 0
    ]
    if not city_relatives:
        return None
    return sum(city_relatives) / len(city_relatives)


def _coverage_report(present_codes: list[str]) -> tuple[float, str]:
    total_w = sum(d["weight"] for d in TUIK_WEIGHTS.values())
    covered_w = sum(TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS)
    coverage_pct = covered_w / total_w * 100 if total_w else 0.0

    lines = [f"Covered TUIK basket: {coverage_pct:.2f}%"]
    for code in sorted(TUIK_WEIGHTS):
        status = "✓" if code in present_codes else "✗"
        name = TUIK_WEIGHTS[code]["name"][:35]
        weight = TUIK_WEIGHTS[code]["weight"]
        lines.append(f"  {code}  {name:<35}  {weight:>6.2f}%  {status}")
    return coverage_pct, "\n".join(lines)


# ── Core metric computation ───────────────────────────────────────────────────

def _dist_stats(rel: pd.Series) -> dict:
    """Distribution stats for a series of per-product percentage changes.

    median_nonzero captures the typical magnitude of change among products
    that actually repriced, since most products show 0% change between
    snapshots and dominate the plain median.
    """
    if rel.empty:
        return {"median_nonzero": None, "pct_increased": None, "pct_decreased": None, "pct_unchanged": None}
    nonzero = rel[rel.abs() > _ZERO_CHANGE_TOL]
    return {
        "median_nonzero": float(nonzero.median()) if not nonzero.empty else None,
        "pct_increased": float((rel > _ZERO_CHANGE_TOL).mean() * 100),
        "pct_decreased": float((rel < -_ZERO_CHANGE_TOL).mean() * 100),
        "pct_unchanged": float((rel.abs() <= _ZERO_CHANGE_TOL).mean() * 100),
    }


def _compute_metrics(
    df_current: pd.DataFrame,
    df_past: pd.DataFrame,
) -> tuple[pd.DataFrame, float | None, float | None, float | None, float | None, dict, dict]:
    if df_past.empty:
        return pd.DataFrame(), None, None, None, None, {}, {}

    merge_keys = ["store", "canonical_key", "tuik_category", "sector"]
    past_sub = df_past[merge_keys + ["price"]].rename(columns={"price": "past_price"})
    matched = df_current.merge(past_sub, on=merge_keys, how="inner")

    if matched.empty:
        return pd.DataFrame(), None, None, None, None, {}, {}

    # Relative change per (store, product): percentage form
    matched["relative"] = (matched["price"] / matched["past_price"] - 1) * 100
    matched["relative"] = matched["relative"].replace([float("inf"), float("-inf")], pd.NA)

    # Drop outliers likely caused by scraping errors (e.g. prices recorded at 10× scale)
    n_before_outlier = matched["relative"].notna().sum()
    matched.loc[matched["relative"].abs() > _OUTLIER_THRESHOLD, "relative"] = pd.NA
    matched.loc[matched["relative"].isna(), ["price", "past_price"]] = pd.NA
    n_dropped = n_before_outlier - matched["relative"].notna().sum()
    if n_dropped:
        logger.info("  Outlier filter: dropped %d product-store pairs with |change| > %.0f%%", n_dropped, _OUTLIER_THRESHOLD)

    # Step 1: average across stores → one row per (canonical_key, tuik_category, sector).
    # Tracks price and past_price so we can build a deduped price index later.
    product_rel = (
        matched
        .groupby(["canonical_key", "tuik_category", "sector"], as_index=False)
        .agg(
            product_key=("product_key", "first"),
            store=("store", lambda s: ",".join(sorted(s.unique()))),
            relative=("relative", "mean"),
            price=("price", "mean"),
            past_price=("past_price", "mean"),
        )
    )

    # Step 2: collapse across sectors → one row per (canonical_key, tuik_category).
    # HomeGoods and ConstructionSupplies both map to TUIK "05"; without this second
    # groupby the same physical product would count twice in all overall metrics.
    product_deduped = (
        product_rel[product_rel["relative"].notna()]
        .groupby(["canonical_key", "tuik_category"], as_index=False)
        .agg(
            product_key=("product_key", "first"),
            relative=("relative", "mean"),
            price=("price", "mean"),
            past_price=("past_price", "mean"),
        )
    )

    # basic_index: basket-level sum ratio using deduped product prices
    sum_cur  = product_deduped["price"].sum()
    sum_past = product_deduped["past_price"].sum()
    basic_index = float((sum_cur / sum_past - 1) * 100) if sum_past else None

    # avg_inflation: arithmetic mean of per-product relatives (deduped)
    valid_rel = product_deduped["relative"].dropna()
    avg_inflation = float(valid_rel.mean()) if not valid_rel.empty else None

    # median_inflation: median of per-product relatives (deduped)
    median_inflation = float(valid_rel.median()) if not valid_rel.empty else None

    # Distribution stats: nonzero median + share increased/decreased/unchanged
    dist_stats = _dist_stats(valid_rel)

    # tuik_weighted: category-level TUIK-weighted average (deduped)
    cat_rel = product_deduped.groupby("tuik_category")["relative"].mean()
    present_codes = list(cat_rel.dropna().index)
    norm_w = normalised_weights(present_codes)
    missing_codes = [c for c in TUIK_WEIGHTS if c not in present_codes]
    if missing_codes:
        missing_weight = sum(TUIK_WEIGHTS[c]["weight"] for c in missing_codes)
        logger.debug(
            "tuik_weighted: %d TUIK categories absent (%s, combined weight %.2f%%) — "
            "their weight is redistributed proportionally to tracked categories.",
            len(missing_codes), ",".join(sorted(missing_codes)), missing_weight,
        )
    tuik_weighted = (
        float(sum(cat_rel[c] * norm_w[c] / 100.0 for c in norm_w if pd.notna(cat_rel.get(c))))
        if norm_w else None
    )

    # Per-category metrics: derive s_basic from product_deduped (deduped prices per category)
    sector_metrics: dict[str, dict] = {}
    for code, grp in product_deduped.groupby("tuik_category"):
        s_cur  = grp["price"].sum()
        s_past = grp["past_price"].sum()
        s_basic = float((s_cur / s_past - 1) * 100) if s_past else None
        s_rel = grp["relative"].dropna()
        s_avg = float(s_rel.mean()) if not s_rel.empty else None
        s_median = float(s_rel.median()) if not s_rel.empty else None
        s_median_nonzero = _dist_stats(s_rel)["median_nonzero"]
        sector_metrics[str(code)] = {
            "basic_index": s_basic,
            "avg_inflation": s_avg,
            "median_inflation": s_median,
            "median_inflation_nonzero": s_median_nonzero,
        }

    return product_deduped, basic_index, avg_inflation, median_inflation, tuik_weighted, sector_metrics, dist_stats


# ── Main calculate function ───────────────────────────────────────────────────

def calculate_turkey_inflation(
    target_date: str | None = None,
    compare_date: str | None = None,
) -> None:
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    logger.info("Loading current data for %s …", today_str)
    df_current, stores_today, n_before = _load_all_stores(today_str)

    if df_current.empty:
        logger.warning("No data found for %s — aborting.", today_str)
        return

    logger.info(
        "Loaded %d stores, %d raw rows, %d unique (store, product) pairs",
        len(stores_today), n_before, len(df_current),
    )

    # Compute rent cities once — used for coverage log, summary metadata, and every interval.
    rent_cities = _rent_city_prices(today_str)

    # Coverage is reported from product data only; group 04 (rent) is not included here
    # because it only enters metrics when past rent data is also available for the interval.
    present_codes = list(df_current["tuik_category"].unique())
    coverage_pct, coverage_str = _coverage_report(present_codes)
    full_coverage_pct, _ = _coverage_report(present_codes + (["04"] if rent_cities else []))
    logger.info("\n%s", coverage_str)
    if rent_cities:
        logger.info(
            "  Rent data present for %s (%d cities, group 04 weight %.2f%%) "
            "— will be included in tuik_weighted_full when past data allows.",
            today_str, len(rent_cities), TUIK_WEIGHTS["04"]["weight"],
        )

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    if compare_date:
        intervals = {"compare": compare_date}
        effective_compare_date = compare_date
    else:
        intervals = {
            f"{days}d": (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            for days in [15, 30]
        }
        effective_compare_date = min(intervals.values())

    category_store_counts = df_current.groupby("tuik_category")["store"].nunique()
    category_product_counts = df_current.groupby("tuik_category")["canonical_key"].nunique()

    summary_row: dict = {
        "date": today_str,
        "compare_date": effective_compare_date,
        "n_stores": len(stores_today),
        "n_products_raw": n_before,  # store×product row count before intra-store dedup
        "n_products_deduped": int(df_current[["canonical_key", "tuik_category"]].drop_duplicates().shape[0]),
        "basket_coverage_pct": round(coverage_pct, 2),
        "basket_coverage_full_pct": round(full_coverage_pct, 2),
    }
    for code, cnt in category_store_counts.items():
        summary_row[f"n_stores_{code}"] = int(cnt)
    if rent_cities:
        summary_row["n_stores_04"] = len(rent_cities)
    for code, cnt in category_product_counts.items():
        summary_row[f"n_products_{code}"] = int(cnt)

    # Detail base: one row per unique (canonical_key, tuik_category) at current date
    detail_base = (
        df_current
        .groupby(["canonical_key", "tuik_category", "sector"], as_index=False)
        .agg(
            product_key=("product_key", "first"),
            store=("store", lambda s: ",".join(sorted(s.unique()))),
        )
    )

    for label, past_str in intervals.items():
        logger.info("Computing interval %s (vs %s) …", label, past_str)
        df_past, _, _ = _load_all_stores(past_str)

        if df_past.empty:
            logger.info("  No past data for %s — skipping interval %s.", past_str, label)
            for key in ["avg_inflation", "median_inflation", "median_inflation_nonzero",
                        "pct_increased", "pct_decreased", "pct_unchanged",
                        "basic_index", "tuik_weighted_products",
                        "tuik_weighted_full", "n_products_matched"]:
                summary_row[f"{key}_{label}"] = None
            continue

        product_deduped, basic_idx, avg_inf, median_inf, tuik_w_products, sector_metrics, dist_stats = _compute_metrics(df_current, df_past)

        # Attach per-product relative to detail frame
        if not product_deduped.empty:
            rel_col = product_deduped[["canonical_key", "tuik_category", "relative"]].rename(
                columns={"relative": f"relative_{label}"}
            )
            detail_base = detail_base.merge(rel_col, on=["canonical_key", "tuik_category"], how="left")

        summary_row[f"avg_inflation_{label}"] = avg_inf
        summary_row[f"median_inflation_{label}"] = median_inf
        summary_row[f"median_inflation_nonzero_{label}"] = dist_stats.get("median_nonzero")
        summary_row[f"pct_increased_{label}"] = dist_stats.get("pct_increased")
        summary_row[f"pct_decreased_{label}"] = dist_stats.get("pct_decreased")
        summary_row[f"pct_unchanged_{label}"] = dist_stats.get("pct_unchanged")
        summary_row[f"basic_index_{label}"] = basic_idx
        summary_row[f"tuik_weighted_products_{label}"] = tuik_w_products
        summary_row[f"n_products_matched_{label}"] = len(product_deduped)

        # Pass pre-loaded current prices — avoids re-reading disk on every interval.
        rent_inf = _rent_relative(rent_cities, past_str)

        if rent_inf is not None and tuik_w_products is not None:
            cat_rel = product_deduped.groupby("tuik_category")["relative"].mean()
            cat_rel_full = cat_rel.copy()
            cat_rel_full["04"] = rent_inf
            present_all = list(cat_rel_full.dropna().index)
            norm_w_all = normalised_weights(present_all)
            tuik_w_full = float(sum(
                cat_rel_full[c] * norm_w_all[c] / 100.0
                for c in norm_w_all
                if pd.notna(cat_rel_full.get(c))
            )) if norm_w_all else tuik_w_products
        else:
            tuik_w_full = tuik_w_products
        summary_row[f"tuik_weighted_full_{label}"] = tuik_w_full

        # Per-category breakdown
        for code, m in sector_metrics.items():
            summary_row[f"avg_inflation_{code}_{label}"] = m["avg_inflation"]
            summary_row[f"median_inflation_{code}_{label}"] = m["median_inflation"]
            summary_row[f"median_inflation_nonzero_{code}_{label}"] = m["median_inflation_nonzero"]
            summary_row[f"basic_index_{code}_{label}"] = m["basic_index"]
        if rent_inf is not None:
            # Stored under its own key to distinguish from product-level avg_inflation columns.
            summary_row[f"rent_inflation_04_{label}"] = rent_inf

        logger.info(
            "  [%s] basic_index=%s  avg=%s  tuik_products=%s  tuik_full=%s",
            label,
            f"{basic_idx:.3f}%" if basic_idx is not None else "N/A",
            f"{avg_inf:.3f}%"   if avg_inf is not None else "N/A",
            f"{tuik_w_products:.3f}%" if tuik_w_products is not None else "N/A",
            f"{tuik_w_full:.3f}%"     if tuik_w_full is not None else "N/A",
        )

    detail_file = _OUT_DIR / f"turkey_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8")
    logger.info("Saved per-product detail: %s", detail_file)

    summary_file = _OUT_DIR / "turkey_inflation_summary.csv"
    df_new = pd.DataFrame([summary_row])
    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            compare_str = str(summary_row["compare_date"])
            same = (df_existing["date"] == today_str) & (
                df_existing["compare_date"].astype(str) == compare_str
            )
            df_existing = df_existing[~same]
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
            df_final = df_final.sort_values("date").reset_index(drop=True)
            df_final.to_csv(summary_file, index=False, encoding="utf-8")
        else:
            df_new.to_csv(summary_file, index=False, encoding="utf-8")
        logger.info("Updated summary: %s", summary_file)
    except Exception as e:
        logger.error("Failed to write summary: %s", e)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Turkey-wide inflation calculator")
    parser.add_argument(
        "--date", default=None,
        help="Target (current) date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--compare", default=None,
        help="Comparison (past) date in YYYY-MM-DD format for a single arbitrary interval",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    calculate_turkey_inflation(args.date, args.compare)
