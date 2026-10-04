"""
cosmetics_inflation.py — Unified Cosmetics Inflation Calculator

One calculator for every cosmetics retailer, using exactly the same method as
the Turkey-wide calculator (turkey_inflation.py). The metric functions are
IMPORTED from turkey_inflation, not re-implemented, so the two can never drift
apart. Only the data loading is cosmetics-specific, because the cosmetics
scrapers write slightly different CSV layouts.

Method (identical to turkey_inflation.py):
  1. Stage 1 dedup  – duplicate rows of a product inside one store are averaged.
  2. Match          – current vs past snapshot, inner join on
                      (store, canonical product name, TÜİK group, sector).
  3. Outlier filter – pairs with |price change| > 80% are treated as scraping
                      artefacts and excluded (relative AND prices).
  4. Stage 2 dedup  – a product sold by several stores is averaged across stores
                      (equal store weight).
  5. Metrics        – basic_index (Dutot), avg_inflation (Carli), median,
                      median_nonzero, pct_increased/decreased/unchanged and
                      tuik_weighted_products.

Re-normalisation to cosmetics only:
  Every product is assigned to TÜİK COICOP 2018 group 13 (Personal care). The
  TÜİK weights are re-normalised over the groups present in the data, which here
  is only group 13, so its 4.49% basket weight becomes 100%. A consequence worth
  knowing: with a single group, tuik_weighted_products is mathematically equal
  to avg_inflation. It is kept so the output schema matches turkey_inflation.

Data layout handled (InflationItems/Datas/Cosmetics/<Store>/*<YYYY-MM-DD>*.csv):
  - name column   : product_name | product name | isim | urun_adi | name | title
  - price column  : price | product cost | fiyat
  - variant column: if present (Eveshop, L'Occitane) the variant is appended to
                    the product name, so different sizes are not averaged into
                    one product. Placeholder variants ("STD / STD") are ignored.
  - header-less 2-column files (Beymen Beauty) are accepted.
  - "Beymen Beauty" and "BeymenBeauty" folders are treated as one store.
  Files whose rows are partly unreadable are loaded anyway, but a warning is
  logged with the number of rows lost, so a malformed file is never silent.

Output (Inflations/Datas/Cosmetics/):
  cosmetics_inflation_{YYYY-MM-DD}.csv        per-product detail
  cosmetics_inflation_summary.csv             one row per (date, compare_date)
  cosmetics_inflation_store_summary.csv       same metrics per store and interval

Usage:
    python cosmetics_inflation.py                       # today, 15d / 30d
    python cosmetics_inflation.py --date 2026-10-04     # specific date
    python cosmetics_inflation.py --date 2026-10-04 --compare 2026-10-02
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent            # Inflations/Codes/Cosmetics
_CODES_DIR = _THIS_DIR.parent                          # Inflations/Codes
_PROJECT_ROOT = _CODES_DIR.parent.parent               # repository root

# turkey_inflation lives in Inflations/Codes and brings its own tuik_config.
sys.path.insert(0, str(_CODES_DIR))
import turkey_inflation as ti  # noqa: E402

_DATA_ROOT = _PROJECT_ROOT / "InflationItems" / "Datas" / "Cosmetics"
_OUT_DIR = _PROJECT_ROOT / "Inflations" / "Datas" / "Cosmetics"

logger = logging.getLogger(__name__)

TUIK_CODE = "13"          # COICOP 2018: Personal care, social protection, misc.
SECTOR = "cosmetics"

_NAME_ALIASES = ("product_name", "product name", "isim", "urun_adi", "name", "title")
_PRICE_ALIASES = ("price", "product cost", "fiyat", "normal_price")

# Variant labels that carry no information (Shopify placeholders).
_PLACEHOLDER_VARIANTS = {"", "default title", "std / std", "std", "nan"}

# Warn when fewer than this share of a file's data rows could be used.
_MIN_USABLE_ROW_SHARE = 0.99


# ── Loading ───────────────────────────────────────────────────────────────────

def _discover(date_str: str) -> dict[str, Path]:
    """Return {store: csv path} for every store that has a file for date_str."""
    found: dict[str, Path] = {}
    for store_dir in sorted(p for p in _DATA_ROOT.iterdir() if p.is_dir()):
        store = store_dir.name.replace(" ", "")      # "Beymen Beauty" -> "BeymenBeauty"
        if store in found:
            continue
        matches = sorted(store_dir.glob(f"*{date_str}*.csv"))
        if not matches:
            continue
        if len(matches) > 1:
            logger.warning("%s: %d files match %s — using %s",
                           store, len(matches), date_str, matches[0].name)
        found[store] = matches[0]
    return found


def _read_prices(fpath: Path, store: str) -> pd.DataFrame | None:
    """Read one store CSV into the standard columns, tolerating known layouts."""
    try:
        with fpath.open(encoding="utf-8-sig", errors="ignore") as fh:
            first = fh.readline().strip()
            n_data_rows = sum(1 for line in fh if line.strip())

        cols = [c.strip().strip('"').lower() for c in first.split(",")]
        has_header = bool(set(cols) & set(_NAME_ALIASES)) and bool(set(cols) & set(_PRICE_ALIASES))

        if has_header:
            df = pd.read_csv(fpath, dtype=str, on_bad_lines="skip", encoding="utf-8-sig")
            df.columns = [c.strip().lower() for c in df.columns]
            name_col = next(a for a in _NAME_ALIASES if a in df.columns)
            price_col = next(a for a in _PRICE_ALIASES if a in df.columns)
        else:
            # Header-less file where col 0 is product name and col 1 is price:
            # accept if the 2nd field (or last field) looks like a valid price.
            price_candidate = cols[1] if len(cols) > 1 else cols[-1]
            if ti._parse_price(price_candidate) is None:
                logger.warning("%s: %s has no recognisable header — skipped", store, fpath.name)
                return None
            n_data_rows += 1
            df = pd.read_csv(fpath, dtype=str, on_bad_lines="skip", encoding="utf-8-sig",
                             header=None, names=["name", "price"], usecols=[0, 1])
            name_col, price_col = "name", "price"

        names = df[name_col].astype(str).str.strip()
        if "variant" in df.columns:
            variant = df["variant"].fillna("").astype(str).str.strip()
            informative = ~variant.str.lower().isin(_PLACEHOLDER_VARIANTS)
            names = names.where(~informative, names + " - " + variant)

        raw_price = df[price_col]
        out = pd.DataFrame({
            "product_key": names,
            "price": raw_price.map(ti._parse_price),
        })
        # Same rule as turkey_inflation: a leading minus sign is not a valid price.
        out.loc[raw_price.astype(str).str.strip().str.startswith("-"), "price"] = None
        out["canonical_key"] = out["product_key"].map(ti._norm)
        out["store"] = store
        out["sector"] = SECTOR
        out["tuik_category"] = TUIK_CODE
        out = out[out["canonical_key"] != ""].dropna(subset=["price"])
        out = out[out["price"] > 0].reset_index(drop=True)

        if n_data_rows and len(out) / n_data_rows < _MIN_USABLE_ROW_SHARE:
            logger.warning(
                "%s: only %d of %d data rows in %s were usable (%.1f%%) — the file may be malformed",
                store, len(out), n_data_rows, fpath.name, 100 * len(out) / n_data_rows,
            )
        return out if not out.empty else None
    except Exception as exc:
        logger.warning("%s: failed to load %s — %s", store, fpath.name, exc)
        return None


def _load_all(date_str: str) -> tuple[pd.DataFrame, list[str], int]:
    """Load every cosmetics store for a date; apply stage 1 (within-store) dedup."""
    frames = []
    for store, fpath in _discover(date_str).items():
        df = _read_prices(fpath, store)
        if df is not None:
            frames.append(df)

    if not frames:
        return pd.DataFrame(columns=ti._STANDARD_COLS), [], 0

    combined = pd.concat(frames, ignore_index=True)
    n_raw = len(combined)
    stores_ok = sorted(combined["store"].unique())
    deduped = (
        combined
        .groupby(["store", "canonical_key", "tuik_category", "sector"], as_index=False)
        .agg(product_key=("product_key", "first"), price=("price", "mean"))
    )
    return deduped, stores_ok, n_raw


# ── Output helpers ────────────────────────────────────────────────────────────

def _upsert(path: Path, df_new: pd.DataFrame, key_cols: list[str]) -> None:
    """Append df_new to a CSV, replacing existing rows that share the key columns."""
    if path.exists():
        old = pd.read_csv(path)
        new_keys = set(map(tuple, df_new[key_cols].astype(str).values))
        is_dup = old[key_cols].astype(str).apply(tuple, axis=1).isin(new_keys)
        df_new = pd.concat([old[~is_dup], df_new], ignore_index=True)
    df_new.sort_values(key_cols[0]).to_csv(path, index=False, encoding="utf-8")


def _fmt(x) -> str:
    return f"{x:.3f}%" if x is not None else "N/A"


# ── Main calculation ──────────────────────────────────────────────────────────

def calculate_cosmetics_inflation(target_date: str | None = None,
                                  compare_date: str | None = None) -> None:
    base_date = datetime.strptime(target_date, "%Y-%m-%d") if target_date else datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    logger.info("Loading cosmetics data for %s …", today_str)
    df_current, stores_today, n_raw = _load_all(today_str)
    if df_current.empty:
        logger.warning("No cosmetics data found for %s — aborting.", today_str)
        return
    logger.info("Loaded %d stores, %d raw rows, %d unique (store, product) pairs",
                len(stores_today), n_raw, len(df_current))

    weight = ti.TUIK_WEIGHTS[TUIK_CODE]["weight"]
    renorm = ti.normalised_weights([TUIK_CODE])[TUIK_CODE]
    logger.info("TÜİK group %s weight %.2f%% → %.0f%% after cosmetics-only re-normalisation",
                TUIK_CODE, weight, renorm)

    if compare_date:
        intervals = {"compare": compare_date}
        effective_compare = compare_date
    else:
        intervals = {f"{d}d": (base_date - timedelta(days=d)).strftime("%Y-%m-%d") for d in (15, 30)}
        effective_compare = min(intervals.values())

    summary: dict = {
        "date": today_str,
        "compare_date": effective_compare,
        "n_stores": len(stores_today),
        "n_products_raw": n_raw,
        "n_products_deduped": int(df_current["canonical_key"].nunique()),
    }
    store_rows: list[dict] = []

    detail = (
        df_current
        .groupby(["canonical_key", "tuik_category", "sector"], as_index=False)
        .agg(product_key=("product_key", "first"),
             store=("store", lambda s: ",".join(sorted(s.unique()))))
    )

    for label, past_str in intervals.items():
        logger.info("Computing interval %s (vs %s) …", label, past_str)
        df_past, past_stores, _ = _load_all(past_str)

        if df_past.empty:
            logger.info("  No past data for %s — skipping interval %s.", past_str, label)
            for key in ("avg_inflation", "median_inflation", "median_inflation_nonzero",
                        "pct_increased", "pct_decreased", "pct_unchanged",
                        "basic_index", "tuik_weighted_products", "n_products_matched"):
                summary[f"{key}_{label}"] = None
            continue

        (prod, basic, avg, median, tuik_w, _sector_m, dist) = ti._compute_metrics(df_current, df_past)

        if not prod.empty:
            rel = prod[["canonical_key", "tuik_category", "relative"]].rename(
                columns={"relative": f"relative_{label}"})
            detail = detail.merge(rel, on=["canonical_key", "tuik_category"], how="left")

        summary[f"avg_inflation_{label}"] = avg
        summary[f"median_inflation_{label}"] = median
        summary[f"median_inflation_nonzero_{label}"] = dist.get("median_nonzero")
        summary[f"pct_increased_{label}"] = dist.get("pct_increased")
        summary[f"pct_decreased_{label}"] = dist.get("pct_decreased")
        summary[f"pct_unchanged_{label}"] = dist.get("pct_unchanged")
        summary[f"basic_index_{label}"] = basic
        summary[f"tuik_weighted_products_{label}"] = tuik_w
        summary[f"n_products_matched_{label}"] = len(prod)

        logger.info("  [%s] basic_index=%s  avg=%s  tuik_weighted=%s  matched=%d",
                    label, _fmt(basic), _fmt(avg), _fmt(tuik_w), len(prod))

        # Same method, one store at a time.
        for store in stores_today:
            if store not in past_stores:
                continue
            s_prod, s_basic, s_avg, s_median, _, _, s_dist = ti._compute_metrics(
                df_current[df_current["store"] == store],
                df_past[df_past["store"] == store],
            )
            if s_prod.empty:
                continue
            store_rows.append({
                "date": today_str, "compare_date": past_str, "interval": label,
                "store": store, "n_products_matched": len(s_prod),
                "basic_index": s_basic, "avg_inflation": s_avg,
                "median_inflation": s_median,
                "median_inflation_nonzero": s_dist.get("median_nonzero"),
                "pct_increased": s_dist.get("pct_increased"),
                "pct_decreased": s_dist.get("pct_decreased"),
                "pct_unchanged": s_dist.get("pct_unchanged"),
            })

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    detail_file = _OUT_DIR / f"cosmetics_inflation_{today_str}.csv"
    detail.to_csv(detail_file, index=False, encoding="utf-8")
    logger.info("Saved per-product detail: %s", detail_file)

    _upsert(_OUT_DIR / "cosmetics_inflation_summary.csv",
            pd.DataFrame([summary]), ["date", "compare_date"])
    logger.info("Updated summary: %s", _OUT_DIR / "cosmetics_inflation_summary.csv")

    if store_rows:
        _upsert(_OUT_DIR / "cosmetics_inflation_store_summary.csv",
                pd.DataFrame(store_rows), ["date", "compare_date", "interval", "store"])
        logger.info("Updated store summary: %s", _OUT_DIR / "cosmetics_inflation_store_summary.csv")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified cosmetics inflation calculator")
    parser.add_argument("--date", default=None,
                        help="Target (current) date, YYYY-MM-DD (default: today)")
    parser.add_argument("--compare", default=None,
                        help="Comparison (past) date, YYYY-MM-DD, for one custom interval")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_cosmetics_inflation(args.date, args.compare)
