import pandas as pd
import glob
import os
import re
import warnings

warnings.filterwarnings("ignore")


def clean_price(price):
    price = str(price)
    price = price.replace("TL", "")
    price = price.replace(".", "")
    price = price.replace(",", ".")
    price = price.strip()
    return pd.to_numeric(price, errors="coerce")


def load_siirt_data(data_dir):
    all_files = glob.glob(os.path.join(data_dir, "*_Dailyrents.csv"))

    print(f"🔍 Found {len(all_files)} Siirt files in:")
    print(os.path.abspath(data_dir))

    df_list = []

    for file in all_files:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(file))
        if not match:
            print(f"⚠️ Skipping {os.path.basename(file)}: Date not found.")
            continue

        date_str = match.group(1)

        try:
            df = pd.read_csv(file)

            if not {"District", "Rooms", "Price"}.issubset(df.columns):
                print(f"⚠️ Skipping {os.path.basename(file)}: Missing required columns.")
                continue

            df["PriceInt"] = df["Price"].apply(clean_price)
            df = df.dropna(subset=["PriceInt", "Rooms"])

            df["Date"] = pd.to_datetime(date_str)
            df["City"] = "Siirt"

            df_list.append(df)

        except Exception as e:
            print(f"❌ Error reading {file}: {e}")

    if not df_list:
        raise ValueError("No valid Siirt data found.")

    master_df = pd.concat(df_list, ignore_index=True)

    master_df["YearWeek"] = master_df["Date"].dt.strftime("%Y-W%V")
    master_df["YearMonth"] = master_df["Date"].dt.strftime("%Y-%m")

    return master_df


def calculate_inflation(df, time_col):
    grouped = df.groupby([time_col, "Rooms"]).agg(
        AvgPrice=("PriceInt", "mean"),
        ListingCount=("PriceInt", "count")
    ).reset_index()

    grouped = grouped.sort_values(["Rooms", time_col])

    grouped["Room_Inflation_%"] = (
        grouped.groupby("Rooms")["AvgPrice"].pct_change() * 100
    )

    total_listings_per_period = grouped.groupby(time_col)["ListingCount"].transform("sum")
    grouped["Weight"] = grouped["ListingCount"] / total_listings_per_period

    grouped["Weighted_Contribution"] = grouped["Room_Inflation_%"] * grouped["Weight"]

    weighted_inflation = grouped.groupby(time_col)["Weighted_Contribution"].sum().reset_index()
    weighted_inflation.rename(
        columns={"Weighted_Contribution": "Weighted_Inflation_%"},
        inplace=True
    )

    simple_mean = df.groupby(time_col)["PriceInt"].mean().reset_index()
    simple_mean["Normal_Inflation_%"] = simple_mean["PriceInt"].pct_change() * 100

    final_report = pd.merge(
        simple_mean[[time_col, "PriceInt", "Normal_Inflation_%"]],
        weighted_inflation,
        on=time_col
    )

    final_report.rename(columns={"PriceInt": "Overall_Avg_Price"}, inplace=True)

    return final_report.round(2), grouped.round(2)


def generate_siirt_inflation_reports(input_dir, output_dir):
    print("=" * 60)
    print("📈 SIIRT RENT INFLATION ANALYSIS STARTED")
    print("=" * 60)

    try:
        df = load_siirt_data(input_dir)
    except ValueError as e:
        print(f"❌ {e}")
        return

    print(f"✅ Loaded {len(df)} Siirt rental records.")

    daily_overall, daily_rooms = calculate_inflation(df, "Date")
    weekly_overall, weekly_rooms = calculate_inflation(df, "YearWeek")
    monthly_overall, monthly_rooms = calculate_inflation(df, "YearMonth")

    os.makedirs(output_dir, exist_ok=True)

    daily_overall.to_csv(
        os.path.join(output_dir, "Siirt_Daily_Inflation_Report.csv"),
        index=False,
        encoding="utf-8-sig"
    )

    weekly_overall.to_csv(
        os.path.join(output_dir, "Siirt_Weekly_Inflation_Report.csv"),
        index=False,
        encoding="utf-8-sig"
    )

    monthly_overall.to_csv(
        os.path.join(output_dir, "Siirt_Monthly_Inflation_Report.csv"),
        index=False,
        encoding="utf-8-sig"
    )

    daily_rooms.to_csv(
        os.path.join(output_dir, "Siirt_Daily_Room_Based_Report.csv"),
        index=False,
        encoding="utf-8-sig"
    )

    weekly_rooms.to_csv(
        os.path.join(output_dir, "Siirt_Weekly_Room_Based_Report.csv"),
        index=False,
        encoding="utf-8-sig"
    )

    monthly_rooms.to_csv(
        os.path.join(output_dir, "Siirt_Monthly_Room_Based_Report.csv"),
        index=False,
        encoding="utf-8-sig"
    )

    print("\n📊 DAILY REPORT:")
    print(daily_overall.tail(5).to_string(index=False))

    print("\n📈 WEEKLY REPORT:")
    print(weekly_overall.tail(5).to_string(index=False))

    print("\n📅 MONTHLY REPORT:")
    print(monthly_overall.tail(5).to_string(index=False))

    print("\n💾 Reports saved to:")
    print(os.path.abspath(output_dir))


if __name__ == "__main__":
    INPUT_DIRECTORY = r"/Users/efeyildirim/PycharmProjects/PythonProject/temizlenmis_csvler/Rents/Siirt"

    OUTPUT_DIRECTORY = r"/Users/efeyildirim/PycharmProjects/PythonProject/inflation_reports/Rents/Siirt"

    generate_siirt_inflation_reports(
        input_dir=INPUT_DIRECTORY,
        output_dir=OUTPUT_DIRECTORY
    )
