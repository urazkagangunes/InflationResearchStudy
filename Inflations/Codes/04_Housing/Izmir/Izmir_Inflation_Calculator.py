import pandas as pd
import glob
import os
import re
import warnings

# To suppress pct_change warnings in Pandas
warnings.filterwarnings('ignore')


def load_all_data(data_dir="."):
    """Reads all dated files in the folder (e.g., Izmir_2026-03-27.csv)."""
    # Look for any CSV file starting with Izmir_
    all_files = glob.glob(os.path.join(data_dir, "Izmir_*.csv"))

    print(f"🔍 Found {len(all_files)} matching files in:\n   {os.path.abspath(data_dir)}")

    df_list = []
    for file in all_files:
        # Extract the YYYY-MM-DD date from the filename using Regex
        match = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(file))
        if not match:
            continue

        date_str = match.group(1)
        try:
            df = pd.read_csv(file)
            # Check if our 'PriceInt' column exists
            if "PriceInt" in df.columns and "Rooms" in df.columns:
                df["Date"] = pd.to_datetime(date_str)
                df_list.append(df)
            else:
                print(f"⚠️ Skipping {os.path.basename(file)}: Missing 'PriceInt' or 'Rooms' columns.")
        except Exception as e:
            print(f"❌ Error reading {file}: {e}")

    if not df_list:
        raise ValueError("No valid data found! Ensure your CSVs have the 'PriceInt' column.")

    master_df = pd.concat(df_list, ignore_index=True)

    # Create a Week (Year-Week) column (e.g., 2026-W13)
    master_df['YearWeek'] = master_df['Date'].dt.strftime('%Y-W%V')

    # Create a Month (Year-Month) column (e.g., 2026-03)
    master_df['YearMonth'] = master_df['Date'].dt.strftime('%Y-%m')

    return master_df


def calculate_inflation(df, time_col):
    """
    Calculates normal and weighted inflation based on the specified time period (Date, YearWeek, or YearMonth).
    """
    # Step 1: Find average prices and listing counts grouped by time and number of rooms
    grouped = df.groupby([time_col, 'Rooms']).agg(
        AvgPrice=('PriceInt', 'mean'),
        ListingCount=('PriceInt', 'count')
    ).reset_index()

    # Step 2: Calculate the price change (% inflation) for each room type compared to the previous period
    grouped = grouped.sort_values(['Rooms', time_col])
    grouped['Room_Inflation_%'] = grouped.groupby('Rooms')['AvgPrice'].pct_change() * 100

    # Step 3: Find the total number of listings for each period (for weighting)
    total_listings_per_period = grouped.groupby(time_col)['ListingCount'].transform('sum')
    grouped['Weight'] = grouped['ListingCount'] / total_listings_per_period

    # Weighted inflation contribution for that period
    grouped['Weighted_Contribution'] = grouped['Room_Inflation_%'] * grouped['Weight']

    # --- CALCULATING OVERALL MARKET INFLATION ---

    # WEIGHTED INFLATION
    weighted_inflation = grouped.groupby(time_col)['Weighted_Contribution'].sum().reset_index()
    weighted_inflation.rename(columns={'Weighted_Contribution': 'Weighted_Inflation_%'}, inplace=True)

    # NORMAL (SIMPLE) INFLATION (Direct average of all houses)
    simple_mean = df.groupby(time_col)['PriceInt'].mean().reset_index()
    simple_mean['Normal_Inflation_%'] = simple_mean['PriceInt'].pct_change() * 100

    # Merge the results
    final_report = pd.merge(simple_mean[[time_col, 'PriceInt', 'Normal_Inflation_%']],
                            weighted_inflation, on=time_col)

    final_report.rename(columns={'PriceInt': 'Overall_Avg_Price'}, inplace=True)

    # Clean up the report (The first day/week/month change will be NaN)
    final_report = final_report.round(2)

    return grouped, final_report


def generate_inflation_reports(input_dir, output_dir):
    print("\n" + "=" * 50)
    print("📈 INITIATING ECONOMIC ANALYSIS PIPELINE")
    print("=" * 50)
    print("📂 Reading and merging CSV files...")

    try:
        df = load_all_data(input_dir)
    except ValueError as e:
        print(f"❌ {e}")
        return

    print(f"✅ Loaded a total of {len(df)} rental house records.\n")

    # --- DAILY CALCULATIONS ---
    daily_rooms_df, daily_overall_df = calculate_inflation(df, 'Date')

    # --- WEEKLY CALCULATIONS ---
    weekly_rooms_df, weekly_overall_df = calculate_inflation(df, 'YearWeek')

    # --- MONTHLY CALCULATIONS ---
    monthly_rooms_df, monthly_overall_df = calculate_inflation(df, 'YearMonth')

    print("📊 DAILY MARKET INFLATION (Last 5 Days):")
    print(daily_overall_df.tail(5).to_string(index=False))
    print("-" * 60)

    print("\n📈 WEEKLY MARKET INFLATION:")
    print(weekly_overall_df.tail(5).to_string(index=False))
    print("-" * 60)

    print("\n📅 MONTHLY MARKET INFLATION:")
    print(monthly_overall_df.tail(5).to_string(index=False))
    print("-" * 60)

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Save the reports to the specified output directory
    daily_report_path = os.path.join(output_dir, "Daily_Inflation_Report.csv")
    weekly_report_path = os.path.join(output_dir, "Weekly_Inflation_Report.csv")
    monthly_report_path = os.path.join(output_dir, "Monthly_Inflation_Report.csv")

    daily_overall_df.to_csv(daily_report_path, index=False, encoding="utf-8-sig")
    weekly_overall_df.to_csv(weekly_report_path, index=False, encoding="utf-8-sig")
    monthly_overall_df.to_csv(monthly_report_path, index=False, encoding="utf-8-sig")

    print(f"\n💾 Reports successfully saved to:\n➡️  {os.path.abspath(output_dir)}")


if __name__ == "__main__":
    # --- DEFINE EXACT PATHS HERE ---

    # Where the scraper SAVES the raw CSV data:
    INPUT_DIRECTORY = r"C:\Users\onurk\PycharmProjects\InflationResearchStudy\InflationItems\Datas\HousesRent\Izmir"

    # Where the calculator should SAVE the final inflation reports:
    OUTPUT_DIRECTORY = r"C:\Users\onurk\PycharmProjects\InflationResearchStudy\Inflations\Datas\HousesRent\Izmir"

    # Run the pipeline
    generate_inflation_reports(input_dir=INPUT_DIRECTORY, output_dir=OUTPUT_DIRECTORY)