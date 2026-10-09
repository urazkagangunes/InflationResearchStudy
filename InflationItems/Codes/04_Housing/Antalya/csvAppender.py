import csv
import glob
import os
import datetime
import pandas as pd

file_pattern = "batch_*_date_*.csv"
month = datetime.date.today().month
day = datetime.date.today().day
output_file = "Antalya" + str(month) + "_" + str(day) + ".csv"

csv_files = sorted(glob.glob(file_pattern))

if not csv_files:
    print("No batch CSV files found.")
    exit()

with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    writer = None
    for i, filename in enumerate(csv_files):
        with open(filename, 'r', newline='', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            header = next(reader)

            if i == 0:

                writer = csv.writer(outfile)
                writer.writerow(header)


            for row in reader:
                writer.writerow(row)

print(f"Merged {len(csv_files)} files into {output_file}")
df = pd.read_csv(output_file)
df.drop(columns=['Title'], inplace=True)
df.dropna(subset=["Number of Rooms"], inplace=True)
df.to_csv(f"AntalyaRent{str(month)}-{str(day)}.csv", index=False)
