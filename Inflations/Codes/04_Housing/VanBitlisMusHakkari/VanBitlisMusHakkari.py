import os
import glob
import re
import math
import pandas as pd


# ============================================================
# 1. PATH SETTINGS
# ============================================================

project_root = os.path.dirname(os.path.abspath(__file__))

# Bu klasörlerden hangisi varsa onu input olarak kullanır.
# Zip'i açınca klasör adı farklı kaldıysa buraya ekleyebilirsin.
possible_input_dirs = [
    os.path.join(project_root, "Sahibinden - datas updated"),
    os.path.join(project_root, "sahibinden_cleaned"),
    os.path.join(project_root, "Sahibinden"),
]

input_dir = None
for candidate in possible_input_dirs:
    if os.path.exists(candidate):
        input_dir = candidate
        break

if input_dir is None:
    raise FileNotFoundError(
        "Input folder bulunamadı. Şu klasörlerden birini oluştur:\n"
        "- Sahibinden - datas updated\n"
        "- sahibinden_cleaned\n"
        "- Sahibinden"
    )

output_dir = os.path.join(project_root, "outputs_sahibinden")

daily_report_output = os.path.join(output_dir, "Daily_Inflation_Report.csv")
weekly_report_output = os.path.join(output_dir, "Weekly_Inflation_Report.csv")
monthly_report_output = os.path.join(output_dir, "Monthly_Inflation_Report.csv")

daily_bucket_output = os.path.join(output_dir, "Daily_Bucket_Report.csv")
weekly_bucket_output = os.path.join(output_dir, "Weekly_Bucket_Report.csv")
monthly_bucket_output = os.path.join(output_dir, "Monthly_Bucket_Report.csv")

diagnostics_output = os.path.join(output_dir, "Sahibinden_Diagnostics.csv")
suspicious_output = os.path.join(output_dir, "Sahibinden_Suspicious_Changes.csv")
skipped_files_output = os.path.join(output_dir, "Sahibinden_Skipped_Files.csv")

os.makedirs(output_dir, exist_ok=True)


# ============================================================
# 2. CONFIG
# ============================================================

# Kiralık ev datasında aynı ilanı birebir takip edemediğimiz için
# City + District + Rooms seviyesinde fixed-bucket inflation hesaplıyoruz.
BUCKET_COLS = ["City", "District", "Rooms"]

# Bucket içindeki fiyat seviyesi için median daha güvenli.
# İstersen "mean" yapabilirsin.
PRICE_AGG = "median"

# Bir bucket bir dönemden sonraki döneme %50'den fazla değişirse outlier sayılır.
# Kapatmak istersen None yap.
MAX_ABS_BUCKET_CHANGE = 0.50


# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def read_csv_safely(file_path):
    encodings = ["utf-8-sig", "utf-8", "cp1254", "latin1"]
    last_error = None

    for encoding in encodings:
        try:
            return pd.read_csv(file_path, encoding=encoding)
        except Exception as e:
            last_error = e

    raise last_error


def extract_date_from_filename(filename):
    """
    Desteklenen dosya adları:
    2026-03-02.csv
    sahibinden_2026-03-02.csv
    Van_2026-03-02.csv
    """

    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)

    if not match:
        return pd.NaT

    return pd.to_datetime(match.group(1), format="%Y-%m-%d", errors="coerce")


def normalize_text(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)

    return text


def parse_rent_price(value):
    """
    Şunları düzgün çevirir:

    10.000 TL -> 10000
    7.500 TL  -> 7500
    15000 TL  -> 15000
    ₺12.000   -> 12000
    """

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

    # Türk formatı: 1.234,56
    if "," in s and "." in s:
        s = s.replace(".", "")
        s = s.replace(",", ".")

    # 1234,56
    elif "," in s:
        s = s.replace(",", ".")

    # 10.000 gibi kira formatı
    elif "." in s:
        parts = s.split(".")

        # 10.000 / 12.500 / 1.250.000 gibi binlik ayracıysa noktaları sil
        if len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
            s = "".join(parts)

    try:
        number = float(s)
    except ValueError:
        return None

    if not math.isfinite(number) or number <= 0:
        return None

    return number


def weighted_mean(values, weights):
    values = values.dropna()

    if values.empty:
        return None

    weights = weights.reindex(values.index).fillna(0)

    if weights.sum() <= 0:
        return values.mean()

    return (values * weights).sum() / weights.sum()


# ============================================================
# 4. LOAD DATA
# ============================================================

def load_all_data(input_dir):
    all_csv_files = glob.glob(os.path.join(input_dir, "**", "*.csv"), recursive=True)

    print("Project root:", project_root)
    print("Input dir:", input_dir)
    print("Output dir:", output_dir)
    print("Found CSV file count:", len(all_csv_files))

    df_list = []
    diagnostics_rows = []
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
            df.columns = [str(col).strip() for col in df.columns]

            colmap = {col.lower(): col for col in df.columns}

            required_cols = ["city", "district", "rooms", "price"]

            if any(col not in colmap for col in required_cols):
                skipped_rows.append({
                    "File": relative_path,
                    "Reason": f"Required columns missing. Found columns: {df.columns.tolist()}"
                })
                continue

            temp = pd.DataFrame()

            # ÖNEMLİ:
            # Önce satır bazlı columnları oluşturuyoruz.
            # Date'i sonra basıyoruz ki NaT problemi olmasın.
            temp["City"] = df[colmap["city"]].apply(normalize_text)
            temp["District"] = df[colmap["district"]].apply(normalize_text)
            temp["Rooms"] = df[colmap["rooms"]].apply(normalize_text)
            temp["PriceInt"] = df[colmap["price"]].apply(parse_rent_price)
            temp["Date"] = date_value.normalize()
            temp["Source_File"] = relative_path

            raw_row_count = len(temp)

            temp = temp.dropna(subset=["PriceInt"])

            for col in BUCKET_COLS:
                temp = temp[temp[col] != ""]
                temp = temp[temp[col].str.lower() != "nan"]

            valid_row_count = len(temp)

            temp["Bucket_Key"] = temp[BUCKET_COLS].agg(" | ".join, axis=1)

            diagnostics_rows.append({
                "Date": date_value.normalize(),
                "File": relative_path,
                "Raw_Row_Count": raw_row_count,
                "Valid_Row_Count": valid_row_count,
                "Removed_Row_Count": raw_row_count - valid_row_count,
                "Listing_Count": valid_row_count,
                "Bucket_Count": temp["Bucket_Key"].nunique(),
                "Average_Rent": temp["PriceInt"].mean(),
                "Median_Rent": temp["PriceInt"].median()
            })

            df_list.append(temp)

        except Exception as e:
            skipped_rows.append({
                "File": relative_path,
                "Reason": f"Read error: {e}"
            })

    if not df_list:
        raise ValueError("No valid Sahibinden data found.")

    full_df = pd.concat(df_list, ignore_index=True)

    full_df["Week_Start"] = (
        full_df["Date"] - pd.to_timedelta(full_df["Date"].dt.weekday, unit="D")
    )

    full_df["Month_Start"] = full_df["Date"].dt.to_period("M").dt.start_time

    diagnostics_df = pd.DataFrame(diagnostics_rows)
    skipped_df = pd.DataFrame(skipped_rows)

    return full_df, diagnostics_df, skipped_df


# ============================================================
# 5. CALCULATE INFLATION
# ============================================================

def calculate_period_inflation(df, time_col, period_col_name):
    """
    time_col:
    - Date
    - Week_Start
    - Month_Start

    Mantık:
    1. Her period + City + District + Rooms için median kira hesapla.
    2. Aynı bucket'ın önceki period'a göre değişimini bul.
    3. Bucket değişimlerini normal ve weighted olarak ortala.
    """

    grouped = (
        df
        .groupby([time_col] + BUCKET_COLS + ["Bucket_Key"])
        .agg(
            Bucket_Price=("PriceInt", PRICE_AGG),
            ListingCount=("PriceInt", "count")
        )
        .reset_index()
    )

    grouped = grouped.sort_values(["Bucket_Key", time_col])

    grouped["Bucket_Inflation"] = (
        grouped
        .groupby("Bucket_Key")["Bucket_Price"]
        .pct_change()
    )

    grouped["Bucket_Inflation_Percent"] = grouped["Bucket_Inflation"] * 100

    price_matrix = (
        grouped
        .pivot(index=time_col, columns="Bucket_Key", values="Bucket_Price")
        .sort_index()
    )

    count_matrix = (
        grouped
        .pivot(index=time_col, columns="Bucket_Key", values="ListingCount")
        .sort_index()
    )

    change_matrix = (price_matrix / price_matrix.shift(1)) - 1

    summary_rows = []
    suspicious_rows = []

    periods = list(price_matrix.index)

    for i, period in enumerate(periods):
        changes = change_matrix.loc[period].dropna()
        changes = changes[changes.apply(lambda x: math.isfinite(x))]

        compared_count = len(changes)

        if MAX_ABS_BUCKET_CHANGE is not None:
            outlier_mask = changes.abs() > MAX_ABS_BUCKET_CHANGE
        else:
            outlier_mask = pd.Series(False, index=changes.index)

        outlier_changes = changes[outlier_mask]
        clean_changes = changes[~outlier_mask]

        base_period = periods[i - 1] if i > 0 else pd.NaT

        for bucket_key, change_value in outlier_changes.items():
            suspicious_rows.append({
                "Period_Type": period_col_name,
                "Period": period,
                "Base_Period": base_period,
                "Bucket_Key": bucket_key,
                "Base_Price": price_matrix.shift(1).loc[period, bucket_key],
                "Current_Price": price_matrix.loc[period, bucket_key],
                "Bucket_Inflation": change_value,
                "Bucket_Inflation_Percent": change_value * 100
            })

        weights = count_matrix.loc[period]

        if len(clean_changes) == 0:
            normal_inflation = None
            weighted_inflation = None
        else:
            normal_inflation = clean_changes.mean()
            weighted_inflation = weighted_mean(clean_changes, weights)

        period_df = df[df[time_col] == period]

        summary_rows.append({
            period_col_name: period,
            "Overall_Avg_Rent": period_df["PriceInt"].mean(),
            "Overall_Median_Rent": period_df["PriceInt"].median(),

            # Decimal hali: 0.012 = %1.2
            "Normal_Inflation": normal_inflation,
            "Weighted_Inflation": weighted_inflation,

            # Yüzde hali: 1.2 = %1.2
            "Normal_Inflation_Percent": (
                None if normal_inflation is None else normal_inflation * 100
            ),
            "Weighted_Inflation_Percent": (
                None if weighted_inflation is None else weighted_inflation * 100
            ),

            "Compared_Bucket_Count": compared_count,
            "Used_Bucket_Count": len(clean_changes),
            "Excluded_Outlier_Bucket_Count": len(outlier_changes),
            "Listing_Count": len(period_df),
            "Bucket_Count": period_df["Bucket_Key"].nunique()
        })

    summary_df = pd.DataFrame(summary_rows)
    suspicious_df = pd.DataFrame(suspicious_rows)

    return grouped, summary_df, suspicious_df


# ============================================================
# 6. MAIN PIPELINE
# ============================================================

def generate_reports():
    print("\n" + "=" * 60)
    print("SAHIBINDEN RENT INFLATION PIPELINE")
    print("=" * 60)

    try:
        df, diagnostics_df, skipped_df = load_all_data(input_dir)
    except ValueError as e:
        print("ERROR:", e)
        return

    print()
    print("Loaded row count:", len(df))
    print("Date range:", df["Date"].min(), "to", df["Date"].max())
    print("Unique bucket count:", df["Bucket_Key"].nunique())

    daily_bucket_df, daily_report_df, daily_suspicious_df = calculate_period_inflation(
        df=df,
        time_col="Date",
        period_col_name="Date"
    )

    weekly_bucket_df, weekly_report_df, weekly_suspicious_df = calculate_period_inflation(
        df=df,
        time_col="Week_Start",
        period_col_name="Week_Start"
    )

    monthly_bucket_df, monthly_report_df, monthly_suspicious_df = calculate_period_inflation(
        df=df,
        time_col="Month_Start",
        period_col_name="Month_Start"
    )

    suspicious_df = pd.concat(
        [daily_suspicious_df, weekly_suspicious_df, monthly_suspicious_df],
        ignore_index=True
    )

    # Export reports
    daily_report_df.to_csv(daily_report_output, index=False, encoding="utf-8-sig")
    weekly_report_df.to_csv(weekly_report_output, index=False, encoding="utf-8-sig")
    monthly_report_df.to_csv(monthly_report_output, index=False, encoding="utf-8-sig")

    daily_bucket_df.to_csv(daily_bucket_output, index=False, encoding="utf-8-sig")
    weekly_bucket_df.to_csv(weekly_bucket_output, index=False, encoding="utf-8-sig")
    monthly_bucket_df.to_csv(monthly_bucket_output, index=False, encoding="utf-8-sig")

    diagnostics_df.to_csv(diagnostics_output, index=False, encoding="utf-8-sig")
    suspicious_df.to_csv(suspicious_output, index=False, encoding="utf-8-sig")
    skipped_df.to_csv(skipped_files_output, index=False, encoding="utf-8-sig")

    print()
    print("Success!")
    print("Daily report:", daily_report_output)
    print("Weekly report:", weekly_report_output)
    print("Monthly report:", monthly_report_output)
    print("Diagnostics:", diagnostics_output)
    print("Suspicious changes:", suspicious_output)
    print("Skipped files:", skipped_files_output)

    print()
    print("Daily report last 5 rows:")
    print(daily_report_df.tail(5).to_string(index=False))

    print()
    print("Weekly report:")
    print(weekly_report_df.tail(10).to_string(index=False))

    print()
    print("Monthly report:")
    print(monthly_report_df.to_string(index=False))


if __name__ == "__main__":
    generate_reports()