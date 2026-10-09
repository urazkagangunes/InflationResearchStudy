import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import glob




DATA_FOLDER = "C:\\Users\\ASUS\\PyCharmMiscProject\\data"

def get_date_from_filename(file):
    name = os.path.basename(file)
    date = name.replace("arden_urunler_", "").replace(".csv","")
    return pd.to_datetime(date)

def clean_price_column(df):
    df["fiyat"] = (
        df["fiyat"]
        .astype(str)
        .str.replace("₺", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    df["fiyat"] = pd.to_numeric(df["fiyat"], errors="coerce")
    return df

def get_daily_averages():
    records = []

    for file_path in glob.glob(DATA_FOLDER + "/*.csv"):

        df = pd.read_csv(file_path)
        df = clean_price_column(df)

        date = get_date_from_filename(file_path)
        avg_price = df["fiyat"].mean()

        records.append({
            "date" :date,
            "average_price": avg_price
        })

    result = pd.DataFrame(records).sort_values("date")
    return result

def percentage_change(date1, date2):
    df = get_daily_averages()
    d1 = pd.to_datetime(date1)
    d2 = pd.to_datetime(date2)

    filtered = df[(df["date"] >= d1) & (df["date"] <= d2)]

    first_avg = filtered.iloc[0]["average_price"]
    last_avg = filtered.iloc[-1]["average_price"]

    return ((last_avg - first_avg) / first_avg) *100

change = percentage_change("2026-03-02", "2026-03-13")

print(f"Price average changed by {change:.2f}% between the selected dates.")


def product_based_change(products, date1, date2):
    
    file1 = os.path.join(DATA_FOLDER, f"arden_urunler_{date1}.csv")
    file2 = os.path.join(DATA_FOLDER, f"arden_urunler_{date2}.csv")

    df1 = pd.read_csv(file1)
    df2 = pd.read_csv(file2)

    df1 = clean_price_column(df1)
    df2 = clean_price_column(df2)

    df1 = df1[df1["isim"].isin(products)]
    df2 = df2[df2["isim"].isin(products)]

    merged = pd.merge(
        df1[["isim", "fiyat"]],
        df2[["isim","fiyat"]],
        on = "isim",
        suffixes=("_old" , "_new")
    )

    merged["change_percent"] = (
        (merged["fiyat_new"] - merged["fiyat_old"])
        / merged["fiyat_old"]
    ) *100

    return merged


result = product_based_change(["Dana Rosto Kg"], "2026-03-02", "2026-03-12")
print(result)
