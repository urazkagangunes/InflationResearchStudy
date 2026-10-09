import os
import glob
import re
import pandas as pd


script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..', '..'))

input_dir = os.path.join(project_root, 'InflationItems', 'Datas', 'Markets', 'Kale')
output_dir = os.path.join(project_root, 'Inflations', 'Datas', 'Markets', 'Kale')
output_filename = os.path.join(output_dir, 'Kale_inflation_summary.csv')

os.makedirs(output_dir, exist_ok=True)


def clean_price(value):

    value = str(value).strip()

    value = (
        value
        .replace('TL', '')
        .replace('₺', '')
        .replace(',', '.')
        .strip()
    )

  
    match = re.search(r'\d+\.\d{2}', value)

    if match:
        return float(match.group())

    return None



file_pattern = os.path.join(
    input_dir,
    'kalemarketleri_prices_*.csv'
)

all_files = glob.glob(file_pattern)

if not all_files:
    print(f"No files found in {input_dir}")

else:

    df_list = []

    for file in all_files:

        filename = os.path.basename(file)

    
        date_str = (
            filename
            .replace('kalemarketleri_prices_', '')
            .replace('.csv', '')
        )

        try:

            
            df = pd.read_csv(file)

            df.columns = df.columns.str.strip()

            if 'product_price' not in df.columns:
                print(f"Missing product_price in {filename}")
                print(df.columns.tolist())
                continue

            
            df['Date'] = pd.to_datetime(date_str)

            
            df['Active_Price'] = (
                df['product_price']
                .apply(clean_price)
            )

            df = df.dropna(subset=['Active_Price'])

           
            df['Category'] = 'Genel_Market'

            df_list.append(df)

        except Exception as e:
            print(f"Error reading {filename}: {e}")

    
    if df_list:

        full_data = pd.concat(
            df_list,
            ignore_index=True
        )

        
        category_prices = (
            full_data
            .groupby(['Date', 'Category'])['Active_Price']
            .mean()
            .unstack()
        )

        category_counts = (
            full_data
            .groupby(['Date', 'Category'])['Active_Price']
            .count()
            .unstack()
        )

        working_prices_df = category_prices.copy()

        

        
        working_prices_df['Overall_Normal'] = (
            category_prices.mean(axis=1)
        )

        working_prices_df['Overall_Weighted'] = (
            (category_prices * category_counts).sum(axis=1)
            / category_counts.sum(axis=1)
        )

        

        daily_inflations = working_prices_df.pct_change()


        weekly_inflations = working_prices_df.pct_change(periods=7)


        daily_inflations = daily_inflations.add_suffix(
            '_Daily_Inflation'
        )

        weekly_inflations = weekly_inflations.add_suffix(
            '_Weekly_Inflation'
        )

        final_export_df = pd.concat(
            [daily_inflations, weekly_inflations],
            axis=1
        )

       
       
        cols = final_export_df.columns.tolist()

        overall_cols = [
            c for c in cols if 'Overall' in c
        ]

        category_cols = sorted([
            c for c in cols if 'Overall' not in c
        ])

        final_export_df = final_export_df[
            overall_cols + category_cols
        ]

        
        
        final_export_df.to_csv(output_filename)

        print(
            f"Success! Saved to: {output_filename}"
        )

    else:
        print("No valid data found.")   
