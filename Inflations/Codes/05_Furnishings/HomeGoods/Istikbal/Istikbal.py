import os
import glob
import pandas as pd

# ==========================================
# 1. SETUP PATHS
# ==========================================
script_dir = os.path.dirname(os.path.abspath(__file__))
# Repo root and category folder come from this file's path
# (Inflations/Codes/<category>/Istikbal), so they hold in any category layout.
_parts = script_dir.split(os.sep)
_root = _parts.index('Inflations')
project_root = os.sep.join(_parts[:_root])
category_dir = os.path.join(*_parts[_root + 2:-1])

# Updated paths for Istikbal
input_dir = os.path.join(project_root, 'InflationItems', 'Datas', category_dir, 'Istikbal')
output_dir = os.path.join(project_root, 'Inflations', 'Datas', category_dir, 'Istikbal')
output_filename = os.path.join(output_dir, 'Istikbal_inflation_summary.csv')

os.makedirs(output_dir, exist_ok=True)

# ==========================================
# 2. READ AND PROCESS DATA
# ==========================================
file_pattern = os.path.join(input_dir, 'istikbal_*.csv')
all_files = glob.glob(file_pattern)

if not all_files:
    print(f"No files found in {input_dir}.")
else:
    df_list = []

    for file in all_files:
        filename = os.path.basename(file)
        # Extract date from filename: istikbal_2026_05_23.csv -> 2026-05-23
        date_str = filename.replace('istikbal_', '').replace('.csv', '').replace('_', '-')

        try:
            df = pd.read_csv(file, encoding='utf-8-sig')
            df = df.rename(columns={'product_name': 'Product Name', 'price': 'Price'})
            df['Date'] = pd.to_datetime(date_str)

            # --- CRITICAL STRING CLEANING FOR ISTIKBAL ---
            if 'Price' in df.columns:
                # 1. Extract ONLY the first matching price pattern (e.g., "62.700,00" or "10.208,00")
                # This safely ignores words like "Sepette" and the "TL" currency label.
                extracted_price = df['Price'].astype(str).str.extract(r'(\d{1,3}(?:\.\d{3})*,\d{2})')[0]

                # 2. Clean that isolated string and convert to float
                df['Active_Price'] = (
                    extracted_price
                    .str.replace('.', '', regex=False)  # Remove thousands separator
                    .str.replace(',', '.', regex=False)  # Convert decimal comma to dot
                    .astype(float)  # Turn into workable math number
                )
            else:
                print(f"Warning: No 'Price' column found in {filename}. Skipping.")
                continue

            df['Name_Key'] = df['Product Name'].astype(str).str.split().str.join(' ').str.casefold()

            # Handle missing categories in Istikbal data (filled after all files are read)
            if 'Category' not in df.columns:
                df['Category'] = pd.NA

            df_list.append(df)

        except Exception as e:
            print(f"Error reading {filename}: {e}")

    # ==========================================
    # 3. MATCHED PRODUCTS
    # ==========================================
    if df_list:
        full_data = pd.concat(df_list, ignore_index=True)

        # Newer files have no Category: reuse the latest known category of the same product name
        known = full_data.dropna(subset=['Category']).sort_values('Date')
        latest_category = known.groupby('Name_Key')['Category'].last()
        full_data['Category'] = full_data['Category'].fillna(full_data['Name_Key'].map(latest_category))
        full_data['Category'] = full_data['Category'].fillna('Genel_Mobilya')

        # One price per product and day; a product listed under several categories
        # (or twice) counts once, in its latest category. "0,00 TL" is not a price.
        priced = full_data[full_data['Active_Price'] > 0]
        prices = priced.groupby(['Date', 'Name_Key'])['Active_Price'].mean().unstack()
        product_category = priced.sort_values('Date').groupby('Name_Key')['Category'].last()

        def basket_change(current, base):
            """Price change of the products present on both days.

            Per category and Overall_Normal: change of the average price of the
            matched products (Overall_Normal averages the category averages);
            Overall_Weighted: change of their total price.
            """
            both = current.notna() & base.notna()
            cur, old = current[both], base[both]
            categories = product_category.reindex(cur.index)
            cur_avg = cur.groupby(categories).mean()
            old_avg = old.groupby(categories).mean()
            change = cur_avg / old_avg - 1
            change['Overall_Normal'] = cur_avg.mean() / old_avg.mean() - 1
            change['Overall_Weighted'] = cur.sum() / old.sum() - 1
            return change

        # ==========================================
        # 4. CALCULATE INFLATIONS & EXPORT
        # ==========================================
        # Daily compares with the previous file, weekly with the file 7 files back.
        dates = prices.index
        daily_inflations = pd.DataFrame(
            {dates[i]: basket_change(prices.iloc[i], prices.iloc[i - 1]) for i in range(1, len(dates))}
        ).T.reindex(dates)
        weekly_inflations = pd.DataFrame(
            {dates[i]: basket_change(prices.iloc[i], prices.iloc[i - 7]) for i in range(7, len(dates))}
        ).T.reindex(dates)
        daily_inflations.index.name = 'Date'
        weekly_inflations.index.name = 'Date'

        daily_inflations = daily_inflations.add_suffix('_Daily_Inflation')
        weekly_inflations = weekly_inflations.add_suffix('_Weekly_Inflation')

        # Join them together
        final_export_df = pd.concat([daily_inflations, weekly_inflations], axis=1)

        # Reorder columns
        cols = final_export_df.columns.tolist()
        overall_cols = [f'Overall_{kind}_{period}_Inflation'
                        for period in ('Daily', 'Weekly') for kind in ('Normal', 'Weighted')]
        category_cols = sorted([c for c in cols if 'Overall' not in c])
        final_export_df = final_export_df.reindex(columns=overall_cols + category_cols)

        # Save to CSV
        final_export_df.to_csv(output_filename)
        print(f"Success! Calculations saved to: {output_filename}")
    else:
        print("No valid data was found to process.")
