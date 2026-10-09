import os

STORE_ID = "25009521"
REGION_ID = "20309457"
LANGUAGE_ID = "-43"
APP_ID = "1"

BASE_URL = "https://www.pullandbear.com"
CATALOG_V2_URL = f"{BASE_URL}/itxrest/2/catalog/store/{STORE_ID}/{REGION_ID}"
CATALOG_V3_URL = f"{BASE_URL}/itxrest/3/catalog/store/{STORE_ID}/{REGION_ID}"

# Lokalde cookie varsa kullan, GitHub Actions'ta cookie olmadan dene
COOKIE = os.environ.get("PB_COOKIE", "")

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Origin": "https://www.pullandbear.com",
    "Referer": "https://www.pullandbear.com/tr/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

if COOKIE:
    HEADERS["Cookie"] = COOKIE

OUTPUT_FILE = "../Datas/ClothingStores/PullandBear/pullandbear_prices.csv"
BATCH_SIZE = 20
