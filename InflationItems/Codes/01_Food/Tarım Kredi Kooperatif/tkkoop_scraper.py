import asyncio
import aiohttp
from bs4 import BeautifulSoup
import csv
from datetime import datetime

base_url = "https://www.tkkoop.com.tr/arama?page={}"
headers = {"User-Agent": "Mozilla/5.0"}

all_products = []
semaphore = asyncio.Semaphore(10)

async def fetch_page(session, page):
    url = base_url.format(page)
    async with semaphore:
        try:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    print(f"Hata {page}: Status {response.status}")
                    return None
                print(f"Çekildi: {page}")
                return await response.text()
        except Exception as e:
            print(f"Hata {page}: {e}")
            return None

def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    products = []

    for card in soup.select(".product-card"):
        name_tag = card.select_one(".product-title")
        price_tag = card.select_one(".ss_urun52")

        if name_tag and price_tag:
            name = name_tag.get("title") or name_tag.get_text(strip=True)
            price = price_tag.get_text(strip=True).replace("TL", "").strip()
            products.append([name, price])

    return products

async def main():
    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:

        tasks = [fetch_page(session, page) for page in range(1, 205)]
        pages = await asyncio.gather(*tasks)

        for html in pages:
            if html:
                products = parse_page(html)
                all_products.extend(products)

    print("Toplam ürün:", len(all_products))

    all_products.sort(key=lambda x: x[0].lower())

    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"Datas/Markets/Tarım Kredi Kooperatif/{today_str}_products.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Ürün Adı", "Fiyat"])
        writer.writerows(all_products)

    print(f"{filename} oluşturuldu ve alfabetik olarak sıralandı.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("Hata oluştu:", e)
        input("Enter ile çık")
