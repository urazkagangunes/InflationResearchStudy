import os
import glob
import pandas as pd

# ==========================================
# 1. SETUP PATHS
# ==========================================
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..', '..'))

# Updated paths for Baskent
input_dir = os.path.join(project_root, 'InflationItems', 'Datas', 'Markets', 'Baskent')
output_dir = os.path.join(project_root, 'Inflations', 'Datas', 'Markets', 'Baskent')
output_filename = os.path.join(output_dir, 'baskent_inflation_summary.csv')

os.makedirs(output_dir, exist_ok=True)

# ==========================================
# 2. READ AND PROCESS DATA
# ==========================================
file_pattern = os.path.join(input_dir, 'baskent_*.csv')
all_files = glob.glob(file_pattern)

if not all_files:
    print(f"No files found in {input_dir}.")
else:
    df_list = []

    for file in all_files:
        filename = os.path.basename(file)
        date_str = filename.replace('baskent_', '').replace('.csv', '')

        try:
            df = pd.read_csv(file)
            df['Date'] = pd.to_datetime(date_str)

            # --- CRITICAL STRING CLEANING FOR BASKENT ---
            # Converts "2.499,00 TL" -> 2499.00
            if 'Price' in df.columns:
                df['Active_Price'] = (
                    df['Price']
                    .astype(str)
                    .str.replace(' TL', '', regex=False)  # Remove currency label
                    .str.replace('.', '', regex=False)  # Remove thousands separator
                    .str.replace(',', '.', regex=False)  # Convert decimal comma to dot
                    .astype(float)  # Turn into workable math number
                )
            else:
                print(f"Warning: No 'Price' column found in {filename}. Skipping.")
                continue

            # Handle missing categories in Baskent data
            if 'Category' not in df.columns:
                df['Category'] = 'Genel_Market'

            df_list.append(df)

        except Exception as e:
            print(f"Error reading {filename}: {e}")

    # ==========================================
    # 3. DYNAMIC WEIGHTS & AVERAGES
    # ==========================================
    if df_list:
        full_data = pd.concat(df_list, ignore_index=True)

        # Create matrices
        category_prices = full_data.groupby(['Date', 'Category'])['Active_Price'].mean().unstack()
        category_counts = full_data.groupby(['Date', 'Category'])['Active_Price'].count().unstack()

        working_prices_df = category_prices.copy()

        # Calculate Overall Normal
        working_prices_df['Overall_Normal'] = category_prices.mean(axis=1)

        # Calculate Overall Weighted (Weights dynamically by item count)
        working_prices_df['Overall_Weighted'] = (category_prices * category_counts).sum(axis=1) / category_counts.sum(
            axis=1)

        # ==========================================
        # 4. CALCULATE INFLATIONS & EXPORT
        # ==========================================
        daily_inflations = working_prices_df.pct_change()
        weekly_inflations = working_prices_df.pct_change(periods=7)

        daily_inflations = daily_inflations.add_suffix('_Daily_Inflation')
        weekly_inflations = weekly_inflations.add_suffix('_Weekly_Inflation')

        # Join them together
        final_export_df = pd.concat([daily_inflations, weekly_inflations], axis=1)

        # Reorder columns
        cols = final_export_df.columns.tolist()
        overall_cols = [c for c in cols if 'Overall' in c]
        category_cols = sorted([c for c in cols if 'Overall' not in c])
        final_export_df = final_export_df[overall_cols + category_cols]

        # Save to CSV
        final_export_df.to_csv(output_filename)
        print(f"Success! Calculations saved to: {output_filename}")
    else:
        print("No valid data was found to process.")