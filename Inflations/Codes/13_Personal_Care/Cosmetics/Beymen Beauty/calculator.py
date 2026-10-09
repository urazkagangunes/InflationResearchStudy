import numpy as np
import pandas as pd
import os
import datetime

month = datetime.datetime.today().month
day = datetime.datetime.today().day


def dataCompiler(raw_df):
    df = raw_df.copy()
    df.columns = [0, 1]
    df[1] = pd.to_numeric(df[1], errors="coerce")
    compiled = df.groupby([0], as_index=False).agg({1: "mean"})

    return compiled


def compareData(new_compiled, old_compiled):
    merged = new_compiled.merge(old_compiled, on=[0], how='left', suffixes=('_new', '_old'))
    merged['1_old'] = merged['1_old'].fillna(merged['1_new'])  # if no old price, treat as unchanged (0% inflation)
    merged['Inflation(%)'] = ((merged['1_new'] - merged['1_old']) / merged['1_old']) * 100
    merged['Inflation(%)'] = merged['Inflation(%)'].fillna(0)
    return merged[[0, 'Inflation(%)']]


def csvSaver(file, timeParam, month, day):
    sum_daily_name = f"InflationData\SummaryData\Daily\\SummaryDailyCosmeticsInflation.csv"
    file_exists = os.path.isfile(sum_daily_name)
    daily_header = not file_exists or os.path.getsize(sum_daily_name) == 0

    sum_monthly_name = f"InflationData\SummaryData\Monthly\\SummaryMonthlyCosmeticsInflation.csv"
    file_exists_month = os.path.isfile(sum_monthly_name)
    monthly_header = not file_exists_month or os.path.getsize(sum_monthly_name) == 0

    sum_weekly_name = f"InflationData\SummaryData\Weekly\\SummaryWeeklyCosmeticsInflation.csv"
    file_exists_week = os.path.isfile(sum_weekly_name)
    weekly_header = not file_exists_week or os.path.getsize(sum_weekly_name) == 0

    newFile = pd.DataFrame()
    newFile[f"{timeParam} Inflation(%)"] = [(file["Inflation(%)"].mean())]
    file[f"{timeParam} Inflation(%)"] = file["Inflation(%)"]
    file = file.drop(columns=["Inflation(%)"])
    newFile["Date"] = [f"{month}-{day}"]

    if timeParam == "Daily":
        file.to_csv(f"InflationData\DetailedInflationData\Daily\\DetailedDailyCosmeticsInflation{month}-{day}.csv",
                    index=False, encoding="utf-8")
        newFile.to_csv(sum_daily_name, index=False, mode="a", encoding="utf-8", header=daily_header)
    if timeParam == "Weekly":
        file.to_csv(f"InflationData\DetailedInflationData\Weekly\\DetailedWeeklyCosmeticsInflation{month}-{day}.csv",
                    index=False, encoding="utf-8")
        newFile.to_csv(sum_weekly_name, index=False, mode="a", encoding="utf-8", header=weekly_header)
    if timeParam == "Monthly":
        file.to_csv(f"InflationData\DetailedInflationData\Monthly\\DetailedMonthlyCosmeticsInflation{month}-{day}.csv",
                    index=False, encoding="utf-8")
        newFile.to_csv(sum_monthly_name, index=False, mode="a", encoding="utf-8", header=monthly_header)


def fileInput(fileNew, fileOld):
    df = pd.read_csv(fileNew)
    df1 = pd.read_csv(fileOld)

    test_1 = dataCompiler(df)
    test_2 = dataCompiler(df1)
    test_3 = compareData(test_1, test_2)

    return test_3


def checkDate(monthNum, dayNum):
    isExtra = False
    try:
        if dayNum > 7:
            test_4 = fileInput(f"Datas\\Cosmetics{str(monthNum)}-{str(dayNum)}.csv",
                               f"Datas\\Cosmetics{str(monthNum)}-{str(dayNum - 7)}.csv")
            csvSaver(test_4, "Weekly", monthNum, dayNum)
        else:
            if (monthNum % 2 == 0 and monthNum <= 7) or (monthNum % 2 == 1 and monthNum > 7) or (monthNum == 8):
                test_4 = fileInput(f"Datas\\Cosmetics{str(monthNum)}-{str(dayNum)}.csv",
                                   f"Datas\\Cosmetics{str(monthNum - 1)}-{str(24 + monthNum)}.csv")
                csvSaver(test_4, "Weekly", monthNum, dayNum)
                isExtra = True
            else:
                test_4 = fileInput(f"Datas\\Cosmetics{str(monthNum)}-{str(dayNum)}.csv",
                                   f"Datas\\Cosmetics{str(monthNum - 1)}-{str(23 + monthNum)}.csv")
                csvSaver(test_4, "Weekly", monthNum, dayNum)
    except Exception as e:
        print(e)
    try:
        if dayNum > 1:
            test_4 = fileInput(f"Datas\\Cosmetics{str(monthNum)}-{str(dayNum)}.csv",
                               f"Datas\\Cosmetics{str(monthNum)}-{str(dayNum - 1)}.csv")
            csvSaver(test_4, "Daily", monthNum, dayNum)
        else:
            if isExtra:
                test_4 = fileInput(f"Datas\\Cosmetics{str(monthNum)}-{str(dayNum)}.csv",
                                   f"Datas\\Cosmetics{str(monthNum - 1)}-{str(31)}.csv")
                csvSaver(test_4, "Daily", monthNum, dayNum)
            else:
                test_4 = fileInput(f"Datas\\Cosmetics{str(monthNum)}-{str(dayNum)}.csv",
                                   f"Datas\\Cosmetics{str(monthNum - 1)}-{str(30)}.csv")
                csvSaver(test_4, "Daily", monthNum, dayNum)
    except Exception as e:
        print(e)
    try:
        if dayNum > 28:
            test_4 = fileInput(f"Datas\\Cosmetics{str(monthNum)}-{str(dayNum)}.csv",
                               f"Datas\\Cosmetics{str(monthNum)}-{str(dayNum - 28)}.csv")
            csvSaver(test_4, "Monthly", monthNum, dayNum)
        else:
            test_4 = fileInput(f"Datas\\Cosmetics{str(monthNum)}-{str(dayNum)}.csv",
                               f"Datas\\Cosmetics{str(monthNum - 1)}-{str(dayNum)}.csv")
            csvSaver(test_4, "Monthly", monthNum, dayNum)
    except Exception as e:
        print(e)

for i in range(29, 31):
    checkDate(4, i)
for i in range(1, 10):
    checkDate(5, i)
