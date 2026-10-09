from __future__ import annotations

import io
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

TITCK_URL = "https://www.titck.gov.tr/dinamikmodul/100"
# SGK optical prices published by the Turkish Opticians' Journal (official SGK rates)
SGK_OPTICAL_URL = (
    "https://www.optikgazete.com/2026-yili-optik-cam-cerceve-banka-ve-kurum-odemeleri"
)
# Target number of successful TİTCK price-list snapshots to collect
MAX_TITCK_FILES = 3
# Max download attempts — some files on the page are not price lists; retry past them
MAX_TITCK_ATTEMPTS = 10
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr,tr-TR;q=0.9,en-US;q=0.8",
}

_SCRIPT_DIR = Path(__file__).resolve().parent
_INFLATION_ITEMS = _SCRIPT_DIR.parents[2]   # InflationItems/Codes/Health/MGL/ → [0]=Health [1]=Codes [2]=InflationItems
OUTPUT_DIR = _INFLATION_ITEMS / "Datas" / "Health" / "Medicine_Glasses_Lenses"
OUTPUT_PATH = OUTPUT_DIR / "health_prices_3months.csv"


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    cleaned = str(text).replace("TL", "").replace("₺", "").replace("\xa0", "").replace(" ", "").strip()
    cleaned = re.sub(r"\([^)]*\)", "", cleaned).strip()  # strip (KDV DÂHİL) etc.
    if "," in cleaned and "." in cleaned:
        # Turkish format: 1.234,56 → 1234.56
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        # Turkish decimal only: 45,50 → 45.50
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        # Dot-only: treat as Turkish thousands separator when exactly 3 digits follow
        # e.g. 1.400 → 1400, but 14.50 → 14.50 (2 digits after dot → decimal)
        idx = cleaned.rfind(".")
        after_dot = cleaned[idx + 1:]
        if len(after_dot) == 3 and after_dot.isdigit() and cleaned[:idx].isdigit():
            cleaned = cleaned.replace(".", "")
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def _classify_optical(name: str) -> str:
    upper = name.upper()
    if any(k in upper for k in ["ÇERÇEVE", "CERCEVE", "FRAME"]):
        return "Gözlük Çerçevesi"
    return "Gözlük Camı"


def _extract_date_from_url(url: str) -> date | None:
    match = re.search(r"(\d{4})[-_.]?(\d{2})[-_.]?(\d{2})", url)
    if match:
        yr = int(match.group(1))
        if 2000 <= yr <= 2099:  # reject UUID-derived pseudo-years like 8496 or 9682
            try:
                return date(yr, int(match.group(2)), int(match.group(3)))
            except ValueError:
                pass  # fall through to archive-year pattern below
    # Fallback: year from /Archive/YYYY/ path (TİTCK URL structure)
    match = re.search(r"/[Aa]rchive/(\d{4})/", url)
    if match:
        try:
            return date(int(match.group(1)), 12, 31)
        except ValueError:
            return None
    return None


def _normalise_medicine_df(df: pd.DataFrame, snapshot_date: date) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    name_col = next(
        (c for c in df.columns if any(k in c.upper() for k in ["İLAÇ", "ILAC", "ÜRÜN", "URUN", "ADI", "NAME"])),
        df.columns[0],
    )
    price_col = next(
        (c for c in df.columns if any(k in c.upper() for k in ["FİYAT", "FIYAT", "PRICE", "PSF", "KDV", "SATIŞ"])),
        None,
    )
    if price_col is None:
        print(f"  ⚠ No price column detected. Columns: {list(df.columns)}")
        return pd.DataFrame()

    result = pd.DataFrame({
        "date": snapshot_date.strftime("%Y-%m-%d"),
        "product-name": df[name_col].astype(str).str.strip(),
        "product-price": df[price_col].apply(lambda x: _parse_price(str(x))),
        "category": "İlaç",
        "source": "TİTCK",
    })
    return result[
        result["product-price"].notna()
        & (result["product-name"] != "")
        & (result["product-name"] != "nan")
    ].reset_index(drop=True)


def fetch_titck_medicine_prices() -> list[pd.DataFrame]:
    """Return a list of DataFrames — one per downloaded TİTCK snapshot (up to MAX_TITCK_FILES)."""
    cutoff = date.today() - timedelta(days=90)

    try:
        resp = requests.get(TITCK_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"⚠ TİTCK unreachable: {exc}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    excel_hrefs = [
        a["href"] for a in soup.find_all("a", href=True)
        if a["href"].lower().endswith((".xls", ".xlsx"))
    ]

    if not excel_hrefs:
        print("⚠ No Excel links found on TİTCK page.")
        return []

    dated: list[tuple[date, str]] = []
    for href in excel_hrefs:
        d = _extract_date_from_url(href)
        if d is None or d >= cutoff:
            dated.append((d or date.today(), href))

    if not dated:
        print("⚠ No files within 3-month window. Using latest available.")
        dated = [(date.today(), h) for h in excel_hrefs[:MAX_TITCK_FILES]]

    # Cap attempts; stop early once we have MAX_TITCK_FILES successful frames
    dated = dated[:MAX_TITCK_ATTEMPTS]

    base = "https://www.titck.gov.tr"
    frames: list[pd.DataFrame] = []
    for snap_date, href in dated:
        if len(frames) >= MAX_TITCK_FILES:
            break
        url = href if href.startswith("http") else base + href
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            r.raise_for_status()
            df = pd.read_excel(io.BytesIO(r.content))
            normed = _normalise_medicine_df(df, snap_date)
            if not normed.empty:
                frames.append(normed)
                print(f"  ✓ {snap_date} — {len(normed):,} medicines")
        except Exception as exc:
            print(f"  ⚠ Skipping {href}: {exc}")

    return frames


def fetch_sgk_optical_prices() -> pd.DataFrame:
    """Fetch SGK official optical reimbursement prices from Optik Gazete (static source)."""
    try:
        resp = requests.get(SGK_OPTICAL_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"⚠ Optik Gazete page unreachable: {exc}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, "html.parser")
    today = date.today().strftime("%Y-%m-%d")
    rows = []
    _HEADER_KEYWORDS = {"KURUM", "KURULUŞ", "ÇERÇEVE", "CAM", "INSTITUTION"}

    # Use only the first table (institution/bank price list); later tables contain
    # diopter-indexed sub-lists that share the same 3-column structure.
    first_table = soup.find("table")
    tables = [first_table] if first_table else []

    for table in tables:
        for tr in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            institution = cells[0].strip()
            # Skip header rows and non-institution rows (diopter ranges like "0-4", "6")
            if not institution or institution.upper() in _HEADER_KEYWORDS:
                continue
            if not any(c.isalpha() for c in institution):
                continue

            frame_price = _parse_price(cells[1])
            lens_price = _parse_price(cells[2])

            if frame_price is not None:
                rows.append({
                    "date": today,
                    "product-name": f"{institution} — Çerçeve",
                    "product-price": frame_price,
                    "category": "Gözlük Çerçevesi",
                    "source": "SGK",
                })
            if lens_price is not None:
                rows.append({
                    "date": today,
                    "product-name": f"{institution} — Cam",
                    "product-price": lens_price,
                    "category": "Gözlük Camı",
                    "source": "SGK",
                })

    if not rows:
        print("⚠ No optical rows parsed from Optik Gazete page.")
    else:
        print(f"  ✓ {len(rows)} optical products from SGK (via Optik Gazete)")

    return pd.DataFrame(rows)


def save_consolidated(
    medicines_df: pd.DataFrame,
    optical_df: pd.DataFrame,
    output_path: Path | None = None,
) -> None:
    if output_path is None:
        output_path = OUTPUT_PATH

    frames = [df for df in (medicines_df, optical_df) if not df.empty]
    if not frames:
        print("❌ No data collected — output file not written.")
        return

    combined = pd.concat(frames, ignore_index=True)
    combined = combined[["product-name", "product-price"]]
    combined = combined.dropna(subset=["product-price"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n✅ {len(combined):,} rows saved → {output_path}")


def _month_start(months_back: int) -> date:
    """Return the first day of the month `months_back` months before today."""
    today = date.today()
    m = today.month - months_back
    y = today.year
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def main() -> None:
    print("=" * 55)
    print("HEALTH PRICES SCRAPER")
    print("=" * 55)

    print("\n💊 Fetching medicine prices from TİTCK...")
    medicine_frames = fetch_titck_medicine_prices()

    print("\n👓 Fetching optical prices from SGK...")
    optical_df = fetch_sgk_optical_prices()

    n = len(medicine_frames)
    if n == 0:
        print("❌ No medicine data — cannot save monthly files.")
        return

    # Assign months oldest-first: frame[0] → n months ago, frame[n-1] → 1 month ago
    for i, med_df in enumerate(medicine_frames):
        months_back = n - 1 - i  # e.g. for n=3: 2, 1, 0 → oldest=2 months ago, newest=current
        month_date = _month_start(months_back)
        month_str = month_date.strftime("%Y-%m")     # e.g. "2026-03"
        date_str = month_date.strftime("%Y-%m-%d")   # e.g. "2026-03-01"

        med = med_df.copy()
        med["date"] = date_str

        opt = optical_df.copy() if not optical_df.empty else pd.DataFrame()
        if not opt.empty:
            opt["date"] = date_str

        output_path = OUTPUT_DIR / f"health_prices_{month_str}.csv"
        print(f"\n📅 {month_str}")
        save_consolidated(med, opt, output_path)


if __name__ == "__main__":
    main()
