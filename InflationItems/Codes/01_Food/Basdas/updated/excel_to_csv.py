import pandas as pd

df = pd.read_excel("basdas_fiyat_takip.xlsx", sheet_name="data")
df.to_csv("basdas_fiyat_takip.csv", index=False, encoding="utf-8")
print("Excel -> CSV tamam.")