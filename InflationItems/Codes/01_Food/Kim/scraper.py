import datetime
import requests
import csv
import time
from bs4 import BeautifulSoup


url = "https://www.kimgeldi.com/Catalog/OBAjaxFilterProducts"
dateM = datetime.datetime.now().month
dateD = datetime.datetime.now().day
def scrapeDaily():


    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.kimgeldi.com/search?cid=1398&adv=True&isc=True&sid=True",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    categories = [{"name": "BİSKÜVİ, ÇİKOLATA, KURUYEMİŞ", "cid": 1193},
                  {"name": "MANAV", "cid": 1398},
                  {"name": "BEBEK MAMA VE BAKIM ÜRÜNLERİ", "cid": 1182},
                  {"name": "YEMEKLİK MALZEMELER", "cid": 1471},
                  {"name": "DETERJAN, TEMİZLİK", "cid": 1216},
                  {"name": "DONDURULMUŞ ÜRÜNLER", "cid": 1240},
                  {"name": "ET, TAVUK, BALIK", "cid": 1258},
                  {"name": "EV, YAŞAM ÜRÜNLER", "cid": 1270},
                  {"name": "İÇECEKLER", "cid": 1320},
                  {"name": "KAĞIT ÜRÜNLERİ", "cid": 1336},
                  {"name": "KİŞİSEL BAKIM, KOZMETİK", "cid": 1353},
                  {"name": "SÜT, KAHVALTILIK", "cid": 1403},
                  {"name": "UNLU MAMÜLLER, PASTANE", "cid": 1453},
                  ]
    Marketdata = []
    session = requests.Session()
    for category in categories:
        for i in range(1, 50000):

            payload = {
                "cid": category["cid"],
                "isc": "true",
                "mid": 0,
                "vid": 0,
                "sid": "true",
                "adv": "true",
                "asv": "false",
                "hmpr": "false",
                "ppr": "false",
                "mev": "false",
                "prp": "false",
                "wsp": "false",
                "Title": category["name"],

                "PagingFilteringContext[PageIndex]": 0,
                "PagingFilteringContext[PageNumber]": i,
                "PagingFilteringContext[PageSize]": 100
            }
            response = session.post(url, headers=headers, data=payload)
            if response.status_code != 200:
                break
            soup = BeautifulSoup(response.text, "html.parser")

            products = soup.find_all("div", class_="details")
            if not products:
                break
            productTitleList = []
            productPriceList = []

            fieldnames = ["title", "price"]
            for product in products:
                productTitleList.append(product.find("h2", {"class": "product-title"}).text.strip())
                productPriceList.append(product.find("span", {"class": "price actual-price"}).text.strip())

            for title, price in zip(productTitleList, productPriceList):
                Marketdata.append([title, price])

        time.sleep(1)

    documentName = "products" + str(dateM)+"-" + str(dateD) + ".csv"
    with open(documentName, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(Marketdata)

scrapeDaily()

