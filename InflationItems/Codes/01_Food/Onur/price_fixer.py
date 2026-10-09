import csv
import os
import re
from typing import Optional


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "..", "..", "Datas", "Markets", "Onur")
)
#change price to float from string

def _normalize_numeric_string(text: str) -> Optional[str]:
    match = re.search(r"[-+]?\d[\d\.,]*", text)
    if not match:
        return None
    number = match.group(0)
    if "," in number and "." in number:
        # Turkish format: thousands "." and decimal ","
        number = number.replace(".", "").replace(",", ".")
    elif "," in number:
        number = number.replace(".", "").replace(",", ".")
    elif "." in number:
        # If the last segment is 1-2 digits, treat "." as decimal separator.
        last = number.split(".")[-1]
        if len(last) in (1, 2):
            number = number.replace(",", "")
        else:
            number = number.replace(".", "")
    return number


def _fix_inflated_price(value: float, raw_text: str) -> float:
    # If a price looks inflated by 100 (e.g., "10990.0" instead of "109.90"),
    # normalize it for grocery-scale prices.
    if value >= 1000 and value.is_integer():
        # Only apply when the raw text doesn't already show explicit decimals.
        has_explicit_decimal = bool(re.search(r"[.,]\d{1,2}\b", raw_text))
        if not has_explicit_decimal and (value / 100) < 1000:
            return value / 100
    return value


def parse_price_to_float(value: str) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = _normalize_numeric_string(text.lower().replace("₺", "").replace("tl", ""))
    if not normalized:
        return None
    try:
        parsed = float(normalized)
    except ValueError:
        return None
    return _fix_inflated_price(parsed, text)


def fix_file(path: str) -> int:
    rows = []
    fixed = 0
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return 0
        rows.append(header)
        for row in reader:
            if not row:
                continue
            if len(row) < 3:
                rows.append(row)
                continue
            price_value = parse_price_to_float(row[2])
            if price_value is not None:
                if str(row[2]) != str(price_value):
                    row[2] = price_value
                    fixed += 1
            rows.append(row)

    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    os.replace(temp_path, path)
    return fixed


def main() -> None:
    if not os.path.isdir(DATA_DIR):
        raise SystemExit(f"Missing data directory: {DATA_DIR}")
    total_fixed = 0
    files = [
        os.path.join(DATA_DIR, name)
        for name in os.listdir(DATA_DIR)
        if name.lower().endswith(".csv")
    ]
    if not files:
        print("No CSV files found.")
        return
    for path in sorted(files):
        fixed = fix_file(path)
        total_fixed += fixed
        print(f"Updated {os.path.basename(path)}: {fixed} rows fixed.")
    print(f"Done. Total rows fixed: {total_fixed}")


if __name__ == "__main__":
    main()
