import numpy as np
import pandas as pd
import regex
import seaborn as sns
import matplotlib.pyplot as plt
import re
import os



def dataCompiler(dataA):
    dataA["Price"] = dataA["Price"].str.replace("TL", "")
    dataA["Price"] = dataA["Price"].str.replace(".", "")
    dataA["Price"] = dataA["Price"].str.strip()
    dataA["Price"] = (dataA["Price"]).astype("float")
    def regexlow(s):
        s=  s.replace("/","")
        return regex.sub(r'(?<!^)(?=\p{Lu})', '/', s,count=1)
    
    for location in dataA["Location"].unique():
        newLoc = (regexlow(location))
        dataA["Location"] = dataA["Location"].replace({location: newLoc})
    dataA_test = dataA.groupby(["Location","Rooms"],as_index=False).agg({"Price":"mean"})
    dataA_test = dataA_test.drop_duplicates(subset=["Location","Rooms"],keep="first")
    return dataA_test

def compareData(dataA,dataB):
    data_test = dataA.merge(dataB, how="left",on=["Location","Rooms"],suffixes=("_x","_y"))
    return data_test


def csvSaver(file,timeParam,month,day):
    sum_daily_name= f"InflationData\SummaryData\Daily\\SummaryDailyRentInflation.csv"
    file_exists = os.path.isfile(sum_daily_name)
    daily_header = not file_exists or os.path.getsize(sum_daily_name) == 0

    sum_monthly_name =f"InflationData\SummaryData\Monthly\\SummaryMonthlyRentInflation.csv"
    file_exists_month = os.path.isfile(sum_monthly_name)
    monthly_header = not file_exists_month or os.path.getsize(sum_monthly_name) == 0

    sum_weekly_name = f"InflationData\SummaryData\Weekly\\SummaryWeeklyRentInflation.csv"
    file_exists_week = os.path.isfile(sum_weekly_name)
    weekly_header = not file_exists_week or os.path.getsize(sum_weekly_name) == 0

    newFile = pd.DataFrame()
    newFile[f"{timeParam} Inflation(%)"] = [(file["Inflation(%)"].mean())]
    file[f"{timeParam} Inflation(%)"] = file["Inflation(%)"]
    file = file.drop(columns=["Inflation(%)"])
    newFile["Date"] = [f"{month}-{day}"]

    if timeParam == "Daily":
        file.to_csv(f"InflationData\DetailedInflationData\Daily\\DetailedDailyRentInflation{month}-{day}.csv",index=False,encoding="utf-8")
        newFile.to_csv(sum_daily_name, index=False ,mode="a",encoding="utf-8",header=daily_header)
    if timeParam == "Weekly":
        file.to_csv(f"InflationData\DetailedInflationData\Weekly\\DetailedWeeklyRentInflation{month}-{day}.csv",index=False,encoding="utf-8")
        newFile.to_csv(sum_weekly_name, index=False ,mode="a",encoding="utf-8",header=weekly_header)
    if timeParam == "Monthly":
        file.to_csv(f"InflationData\DetailedInflationData\Monthly\\DetailedMonthlyRentInflation{month}-{day}.csv", index=False,encoding="utf-8")
        newFile.to_csv(sum_monthly_name, index=False ,mode="a",encoding="utf-8",header=monthly_header)


def fileInput(fileNew,fileOld):
    df = pd.read_csv(fileNew)
    df = df[df["Price"] != "Price"]
    df1 = pd.read_csv(fileOld)
    df1 = df1[df1["Price"] != "Price"]
    test_1 = dataCompiler(df)
    test_2 = dataCompiler(df1)
    test_3 = compareData(test_1, test_2)
    test_3["Inflation(%)"] = ((test_3["Price_x"] - test_3["Price_y"]) / test_3["Price_y"]) * 100
    test_3["Inflation(%)"] = test_3["Inflation(%)"].fillna(0)
    test_3 = test_3.drop(columns=["Price_y", "Price_x"])
    return test_3


#Change as needed
for i in range(10,14):
    test_4 = fileInput(f"Datas\AntalyaRent3-{str(i)}.csv", f"Datas\AntalyaRent3-{str(i-7)}.csv")
    csvSaver(test_4, "Weekly", 3, i)




