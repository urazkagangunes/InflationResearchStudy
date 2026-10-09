import os
import glob
import re
import math
import pandas as pd


# ============================================================
# 1. PATH SETTINGS
# ============================================================

project_root = os.path.dirname(os.path.abspath(__file__))

possible_input_dirs = [
    os.path.join(project_root, "vatancomputer_isim_fiyat_cleaned"),
    os.path.join(project_root, "Vatan Computer - datas updated"),
    os.path.join(project_root, "VatanComputer - datas updated"),
    os.path.join(project_root, "Vatan Computer"),
    os.path.join(project_root, "vatancomputer"),
    os.path.join(project_root, "VatanComputer"),
]

input_dir = None

for candidate in possible_input_dirs:
    if os.path.exists(candidate):
        input_dir = candidate
        break

if input_dir is None:
    raise FileNotFoundError(
        "Vatan Computer input folder bulunamadı. Proje klasörüne şu isimlerden biriyle koy:\n"
        "- vatancomputer_isim_fiyat_cleaned\n"
        "- Vatan Computer - datas updated\n"
        "- VatanComputer - datas updated\n"
        "- Vatan Computer\n"
        "- vatancomputer\n"
        "- VatanComputer"
    )

output_dir = os.path.join(project_root, "outputs_vatancomputer")

summary_output = os.path.join(output_dir, "vatancomputer_inflation_summary.csv")
diagnostics_output = os.path.join(output_dir, "vatancomputer_diagnostics.csv")
suspicious_output = os.path.join(output_dir, "vatancomputer_suspicious_item_changes.csv")
skipped_files_output = os.path.join(output_dir, "vatancomputer_skipped_files.csv")
price_matrix_output = os.path.join(output_dir, "vatancomputer_product_price_matrix.csv")

os.makedirs(output_dir, exist_ok=True)


# ============================================================
# 2. CONFIG
# ============================================================

DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")

# Elektronik ürünlerde kampanya/stok/fiyat güncellemesi olabilir.
# Aynı ürünün kısa sürede %80'den fazla değişmesi çoğunlukla data/ürün eşleşme problemi olabilir.
# Kapatmak istersen None yap.
MAX_ABS_ITEM_CHANGE = 0.80

# Weekly hesapta tam 7 gün önce yoksa, 7 gün öncesine en yakın snapshot aranır.
WEEKLY_TOLERANCE_DAYS = 3


# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def read_csv_safely(file_path):
    encodings = ["utf-8-sig", "utf-8", "cp1254", "latin1"]
    last_error = None

    for encoding in encodings:
        try:
            return pd.read_csv(file_path, sep=";", encoding=encoding)
        except Exception as e:
            last_error = e

    raise last_error


def extract_date_from_filename(filename):
    match = DATE_PATTERN.search(filename)

    if not match:
        return pd.NaT

    return pd.to_datetime(match.group(1), format="%Y-%m-%d", errors="coerce")


def normalize_product_name(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    text = text.casefold()

    return text


def parse_price(value):
    if pd.isna(value):
        return None

    s = str(value).strip()

    s = s.replace("TL", "")
    s = s.replace("₺", "")
    s = s.replace(" ", "")

    # Sadece sayı, nokta ve virgül kalsın
    s = re.sub(r"[^0-9,.]", "", s)

    if s == "":
        return None

    # Türk formatı: 50.499,99
    if "," in s and "." in s:
        s = s.replace(".", "")
        s = s.replace(",", ".")

    # Decimal comma: 50499,99
    elif "," in s:
        s = s.replace(",", ".")

    # 50.499 gibi binlik nokta formatı
    elif "." in s:
        parts = s.split(".")
        if len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
            s = "".join(parts)

    try:
        number = float(s)
    except ValueError:
        return None

    if not math.isfinite(number) or number <= 0:
        return None

    return number


def find_weekly_base_date(current_date, available_dates):
    target_date = current_date - pd.Timedelta(days=7)

    candidates = []

    for date in available_dates:
        if date >= current_date:
            continue

        day_diff = abs((date - target_date).days)

        if day_diff <= WEEKLY_TOLERANCE_DAYS:
            candidates.append((day_diff, date))

    if not candidates:
        return pd.NaT

    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][1]


def calculate_change_for_pair(
    product_prices,
    product_name_lookup,
    current_date,
    base_date,
    change_type
):
    if pd.isna(base_date):
        return {
            "inflation": None,
            "raw_inflation": None,
            "median_inflation": None,
            "compared_count": 0,
            "used_count": 0,
            "excluded_count": 0,
            "suspicious_rows": []
        }

    current_prices = product_prices.loc[current_date]
    base_prices = product_prices.loc[base_date]

    item_changes = (current_prices / base_prices) - 1
    item_changes = item_changes.dropna()
    item_changes = item_changes[item_changes.apply(lambda x: math.isfinite(x))]

    compared_count = len(item_changes)

    if MAX_ABS_ITEM_CHANGE is not None:
        suspicious_mask = item_changes.abs() > MAX_ABS_ITEM_CHANGE
    else:
        suspicious_mask = pd.Series(False, index=item_changes.index)

    suspicious_changes = item_changes[suspicious_mask]
    clean_changes = item_changes[~suspicious_mask]

    suspicious_rows = []

    for product_key, change_value in suspicious_changes.items():
        suspicious_rows.append({
            "Change_Type": change_type,
            "Date": current_date,
            "Base_Date": base_date,
            "Product_Key": product_key,
            "Product_Name": product_name_lookup.get(product_key, product_key),
            "Base_Price": base_prices[product_key],
            "Current_Price": current_prices[product_key],
            "Item_Inflation": change_value,
            "Item_Inflation_Percent": change_value * 100
        })

    clean_mean = None if len(clean_changes) == 0 else clean_changes.mean()
    clean_median = None if len(clean_changes) == 0 else clean_changes.median()
    raw_mean = None if len(item_changes) == 0 else item_changes.mean()

    return {
        "inflation": clean_mean,
        "raw_inflation": raw_mean,
        "median_inflation": clean_median,
        "compared_count": compared_count,
        "used_count": len(clean_changes),
        "excluded_count": len(suspicious_changes),
        "suspicious_rows": suspicious_rows
    }


# ============================================================
# 4. READ DATA
# ============================================================

all_csv_files = glob.glob(os.path.join(input_dir, "**", "*.csv"), recursive=True)

print("Project root:", project_root)
print("Input dir:", input_dir)
print("Output dir:", output_dir)
print("Found CSV file count:", len(all_csv_files))

df_list = []
source_rows = []
skipped_rows = []

for file_path in sorted(all_csv_files):
    filename = os.path.basename(file_path)
    relative_path = os.path.relpath(file_path, input_dir)

    if filename.lower() == "format_fix_report.csv":
        skipped_rows.append({
            "File": relative_path,
            "Reason": "format_fix_report skipped"
        })
        continue

    date_value = extract_date_from_filename(filename)

    if pd.isna(date_value):
        skipped_rows.append({
            "File": relative_path,
            "Reason": "No YYYY-MM-DD date found in filename"
        })
        continue

    try:
        df = read_csv_safely(file_path)

        df.columns = [str(col).strip().lower() for col in df.columns]

        if "isim" not in df.columns or "fiyat" not in df.columns:
            skipped_rows.append({
                "File": relative_path,
                "Reason": f"Required columns not found. Columns: {df.columns.tolist()}"
            })
            continue

        temp = pd.DataFrame()
        temp["Product_Name"] = df["isim"].astype(str).str.strip()
        temp["Product_Key"] = df["isim"].apply(normalize_product_name)
        temp["Active_Price"] = df["fiyat"].apply(parse_price)
        temp["Date"] = date_value.normalize()

        raw_row_count = len(temp)

        temp = temp.dropna(subset=["Active_Price"])
        temp = temp[temp["Product_Key"] != ""]
        temp = temp[temp["Product_Key"] != "nan"]
        temp = temp[temp["Active_Price"] > 0]

        valid_row_count = len(temp)
        unique_item_count = temp["Product_Key"].nunique()
        duplicate_item_count = valid_row_count - unique_item_count

        source_rows.append({
            "Date": date_value.normalize(),
            "File": relative_path,
            "Raw_Row_Count": raw_row_count,
            "Valid_Row_Count": valid_row_count,
            "Unique_Item_Count": unique_item_count,
            "Duplicate_Item_Count": duplicate_item_count,
            "Removed_Row_Count": raw_row_count - valid_row_count
        })

        df_list.append(temp)

    except Exception as e:
        skipped_rows.append({
            "File": relative_path,
            "Reason": f"Read error: {e}"
        })


# ============================================================
# 5. BUILD PRODUCT PRICE MATRIX
# ============================================================

if not df_list:
    print("No valid Vatan Computer data found.")
    pd.DataFrame(skipped_rows).to_csv(
        skipped_files_output,
        index=False,
        encoding="utf-8-sig"
    )
    raise SystemExit

full_data = pd.concat(df_list, ignore_index=True)

print("Used file count:", len(df_list))
print("Total valid product rows:", len(full_data))
print("Date range:", full_data["Date"].min(), "to", full_data["Date"].max())

product_name_lookup = (
    full_data
    .drop_duplicates(subset=["Product_Key"])
    .set_index("Product_Key")["Product_Name"]
    .to_dict()
)

# Aynı gün aynı ürün tekrar ederse median fiyat alınır.
daily_product_prices_long = (
    full_data
    .groupby(["Date", "Product_Key"], as_index=False)["Active_Price"]
    .median()
)

product_prices = (
    daily_product_prices_long
    .pivot(index="Date", columns="Product_Key", values="Active_Price")
    .sort_index()
)

available_dates = list(product_prices.index)

source_df = (
    pd.DataFrame(source_rows)
    .groupby("Date", as_index=False)
    .agg({
        "File": lambda x: " | ".join(map(str, x)),
        "Raw_Row_Count": "sum",
        "Valid_Row_Count": "sum",
        "Unique_Item_Count": "sum",
        "Duplicate_Item_Count": "sum",
        "Removed_Row_Count": "sum"
    })
    .set_index("Date")
    .sort_index()
)

product_prices.to_csv(price_matrix_output, encoding="utf-8-sig")


# ============================================================
# 6. CALCULATE DAILY AND WEEKLY INFLATION
# ============================================================

summary_rows = []
diagnostics_rows = []
all_suspicious_rows = []

for i, current_date in enumerate(available_dates):

    previous_date = pd.NaT if i == 0 else available_dates[i - 1]
    weekly_base_date = find_weekly_base_date(current_date, available_dates)

    daily_result = calculate_change_for_pair(
        product_prices=product_prices,
        product_name_lookup=product_name_lookup,
        current_date=current_date,
        base_date=previous_date,
        change_type="Daily"
    )

    weekly_result = calculate_change_for_pair(
        product_prices=product_prices,
        product_name_lookup=product_name_lookup,
        current_date=current_date,
        base_date=weekly_base_date,
        change_type="Weekly"
    )

    all_suspicious_rows.extend(daily_result["suspicious_rows"])
    all_suspicious_rows.extend(weekly_result["suspicious_rows"])

    daily_inflation = daily_result["inflation"]
    weekly_inflation = weekly_result["inflation"]

    summary_rows.append({
        "Date": current_date,

        "Overall_Normal_Daily_Inflation": daily_inflation,
        "Overall_Weighted_Daily_Inflation": daily_inflation,

        "Overall_Normal_Weekly_Inflation": weekly_inflation,
        "Overall_Weighted_Weekly_Inflation": weekly_inflation,

        "Genel_Electronics_Daily_Inflation": daily_inflation,
        "Genel_Electronics_Weekly_Inflation": weekly_inflation
    })

    current_prices = product_prices.loc[current_date]
    source_info = source_df.loc[current_date].to_dict()

    diagnostics_rows.append({
        "Date": current_date,
        "Source_File": source_info.get("File"),
        "Raw_Row_Count": source_info.get("Raw_Row_Count"),
        "Valid_Row_Count": source_info.get("Valid_Row_Count"),
        "Unique_Item_Count": source_info.get("Unique_Item_Count"),
        "Duplicate_Item_Count": source_info.get("Duplicate_Item_Count"),
        "Removed_Row_Count": source_info.get("Removed_Row_Count"),

        "Previous_Date_For_Daily": previous_date,
        "Weekly_Base_Date": weekly_base_date,

        "Daily_Raw_Inflation": daily_result["raw_inflation"],
        "Daily_Clean_Inflation": daily_result["inflation"],
        "Daily_Median_Inflation": daily_result["median_inflation"],
        "Daily_Compared_Item_Count": daily_result["compared_count"],
        "Daily_Used_Item_Count": daily_result["used_count"],
        "Daily_Excluded_Outlier_Count": daily_result["excluded_count"],

        "Weekly_Raw_Inflation": weekly_result["raw_inflation"],
        "Weekly_Clean_Inflation": weekly_result["inflation"],
        "Weekly_Median_Inflation": weekly_result["median_inflation"],
        "Weekly_Compared_Item_Count": weekly_result["compared_count"],
        "Weekly_Used_Item_Count": weekly_result["used_count"],
        "Weekly_Excluded_Outlier_Count": weekly_result["excluded_count"],

        "Average_Price_Level": current_prices.mean(skipna=True),
        "Median_Price_Level": current_prices.median(skipna=True)
    })


# ============================================================
# 7. EXPORT
# ============================================================

summary_df = pd.DataFrame(summary_rows).set_index("Date")
summary_df.index.name = "Date"

diagnostics_df = pd.DataFrame(diagnostics_rows)
suspicious_df = pd.DataFrame(all_suspicious_rows)
skipped_df = pd.DataFrame(skipped_rows)

summary_df.to_csv(summary_output, encoding="utf-8-sig")
diagnostics_df.to_csv(diagnostics_output, index=False, encoding="utf-8-sig")
suspicious_df.to_csv(suspicious_output, index=False, encoding="utf-8-sig")
skipped_df.to_csv(skipped_files_output, index=False, encoding="utf-8-sig")


# ============================================================
# 8. PRINT RESULT
# ============================================================

print()
print("Success!")
print("Summary saved to:", summary_output)
print("Diagnostics saved to:", diagnostics_output)
print("Suspicious item changes saved to:", suspicious_output)
print("Skipped files saved to:", skipped_files_output)
print("Product price matrix saved to:", price_matrix_output)

print()
print("Skipped file count:", len(skipped_df))

print()
print("Daily inflation min/max:")
print(
    summary_df["Genel_Electronics_Daily_Inflation"].min(),
    summary_df["Genel_Electronics_Daily_Inflation"].max()
)

print()
print("Weekly inflation min/max:")
print(
    summary_df["Genel_Electronics_Weekly_Inflation"].min(),
    summary_df["Genel_Electronics_Weekly_Inflation"].max()
)

daily_series = summary_df["Genel_Electronics_Daily_Inflation"].dropna()

if len(daily_series) > 0:
    cumulative_inflation = (1 + daily_series).prod() - 1

    print()
    print("Cumulative inflation:")
    print(cumulative_inflation)
    print("Cumulative inflation percent:")
    print(cumulative_inflation * 100)