import numpy as np
import pandas as pd
import os
import sys
import datetime

month = datetime.datetime.today().month
day = datetime.datetime.today().day
year = datetime.datetime.today().year

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "InflationItems", "Datas", "HomeGoods",
                        "Ikea")
OUT_DIR = os.path.join(REPO_ROOT, "Inflations", "Datas", "HomeGoods", "Ikea")


def dataFile(date):
    # Spring: HomeGoods<M>-<D>.csv; new scraper: ikea_<YYYY-MM-DD>.csv
    spring = os.path.join(DATA_DIR, f"HomeGoods{date.month}-{date.day}.csv")
    if os.path.isfile(spring):
        return spring
    return os.path.join(DATA_DIR, f"ikea_{date:%Y-%m-%d}.csv")


def dataCompiler(raw_df):
    df = raw_df.copy()
    df.columns = [0, 1]
    df[1] = pd.to_numeric(df[1], errors="coerce")
    compiled = df.groupby([0], as_index=False).agg({1: "mean"})

    return compiled


def compareData(new_compiled, old_compiled):
    merged = new_compiled.merge(old_compiled, on=[0], how='left', suffixes=('_new', '_old'))
    # A product missing from the earlier file has no price change; it stays in the
    # detail file without a value and out of the averages (counting it as 0% pulled
    # every average towards zero).
    merged['Inflation(%)'] = ((merged['1_new'] - merged['1_old']) / merged['1_old']) * 100
    merged['Inflation(%)'] = merged['Inflation(%)'].replace([np.inf, -np.inf], np.nan)
    return merged[[0, 'Inflation(%)']]


def csvSaver(file, timeParam, month, day):
    for folder in ("DetailedInflationData", "SummaryData"):
        os.makedirs(os.path.join(OUT_DIR, folder, timeParam), exist_ok=True)

    sum_daily_name = os.path.join(OUT_DIR, "SummaryData", "Daily",
                                  "SummaryDailyHomeGoodsInflation.csv")
    file_exists = os.path.isfile(sum_daily_name)
    daily_header = not file_exists or os.path.getsize(sum_daily_name) == 0

    sum_monthly_name = os.path.join(OUT_DIR, "SummaryData", "Monthly",
                                    "SummaryMonthlyHomeGoodsInflation.csv")
    file_exists_month = os.path.isfile(sum_monthly_name)
    monthly_header = not file_exists_month or os.path.getsize(sum_monthly_name) == 0

    sum_weekly_name = os.path.join(OUT_DIR, "SummaryData", "Weekly",
                                   "SummaryWeeklyHomeGoodsInflation.csv")
    file_exists_week = os.path.isfile(sum_weekly_name)
    weekly_header = not file_exists_week or os.path.getsize(sum_weekly_name) == 0

    newFile = pd.DataFrame()
    newFile[f"{timeParam} Inflation(%)"] = [(file["Inflation(%)"].mean())]
    file[f"{timeParam} Inflation(%)"] = file["Inflation(%)"]
    file = file.drop(columns=["Inflation(%)"])
    newFile["Date"] = [f"{month}-{day}"]

    if timeParam == "Daily":
        file.to_csv(os.path.join(OUT_DIR, "DetailedInflationData", "Daily",
                                 f"DetailedDailyHomeGoodsInflation{month}-{day}.csv"),
                    index=False, encoding="utf-8")
        newFile.to_csv(sum_daily_name, index=False, mode="a", encoding="utf-8", header=daily_header)
    if timeParam == "Weekly":
        file.to_csv(os.path.join(OUT_DIR, "DetailedInflationData", "Weekly",
                                 f"DetailedWeeklyHomeGoodsInflation{month}-{day}.csv"),
                    index=False, encoding="utf-8")
        newFile.to_csv(sum_weekly_name, index=False, mode="a", encoding="utf-8", header=weekly_header)
    if timeParam == "Monthly":
        file.to_csv(os.path.join(OUT_DIR, "DetailedInflationData", "Monthly",
                                 f"DetailedMonthlyHomeGoodsInflation{month}-{day}.csv"),
                    index=False, encoding="utf-8")
        newFile.to_csv(sum_monthly_name, index=False, mode="a", encoding="utf-8", header=monthly_header)


def fileInput(fileNew, fileOld):
    df = pd.read_csv(fileNew)
    df1 = pd.read_csv(fileOld)

    test_1 = dataCompiler(df)
    test_2 = dataCompiler(df1)
    test_3 = compareData(test_1, test_2)

    return test_3


def compare(date, past, timeParam):
    try:
        test_4 = fileInput(dataFile(date), dataFile(past))
        csvSaver(test_4, timeParam, date.month, date.day)
    except Exception as e:
        print(e)


def checkDate(monthNum, dayNum):
    # Calendar arithmetic: the old month-length guesses asked for dates like
    # 9-33 in the first week of a month and 2-30 on the 1st of March.
    date = datetime.date(year, monthNum, dayNum)
    compare(date, date - datetime.timedelta(days=7), "Weekly")
    compare(date, date - datetime.timedelta(days=1), "Daily")
    if dayNum > 28:
        compare(date, date.replace(day=dayNum - 28), "Monthly")
    else:
        last_month = date.replace(day=1) - datetime.timedelta(days=1)
        compare(date, last_month.replace(day=dayNum), "Monthly")


if __name__ == "__main__":
    # Dates as M-D arguments, e.g. "5-10 5-11"; today's date when none given
    for date in sys.argv[1:] or [f"{month}-{day}"]:
        checkDate(*map(int, date.split("-")))
