"""Historical cigarette news observations; no assumed pack sizes."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from whisky_pilot import clean, money, MONTHS, ROOT

URL = 'https://www.birgun.net/haber/bir-sigara-grubuna-daha-zam-geldi-727813'
FIELDS = ['product_name', 'price', 'quantity', 'quantity_unit', 'currency', 'product_type',
          'collected_at', 'source_published_at', 'source_modified_at', 'effective_from',
          'effective_until', 'source_url', 'validation_status', 'review_reason']

def parse(html, stamp):
    now = datetime.fromisoformat(stamp)
    soup = BeautifulSoup(html, 'html.parser')
    bodies = soup.select('.contentdetail')
    if len(bodies) != 1:
        raise ValueError('Tek haber govdesi bulunamadi.')
    body = bodies[0]
    articles = []
    for script in soup.select('script[type="application/ld+json"]'):
        data = json.loads(script.get_text())
        values = data if isinstance(data,list) else [data]
        for obj in values:
            if isinstance(obj,dict) and obj.get('@type') == 'NewsArticle':
                articles.append(obj)
    if len(articles) != 1:
        raise ValueError('Tek NewsArticle zaman kaydi bulunamadi.')
    article = articles[0]
    dates = {}
    for key in ('datePublished','dateModified'):
        value = article.get(key,'')
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed > now:
            raise ValueError('Gecersiz veya gelecekte haber zamani.')
        dates[key] = value
    if datetime.fromisoformat(dates['dateModified']) < datetime.fromisoformat(dates['datePublished']):
        raise ValueError('Guncelleme yayin zamanindan once.')
    headers = [h for h in body.find_all(['h2','h3'])
               if clean(h.get_text(' ',strip=True)) == 'PHİLİP MORRİS GÜNCEL FİYAT LİSTESİ']
    if len(headers) != 1:
        raise ValueError('Beklenen fiyat listesi basligi yok veya tekrarlandi.')
    listing = None
    introduction = []
    for sibling in headers[0].find_all_next(['h2','h3','p','ul']):
        if body not in sibling.parents:
            break
        if sibling.name in ('h2','h3'):
            break
        if sibling.name == 'ul':
            listing = sibling
            break
        if sibling.name == 'p':
            introduction.append(sibling.get_text(' ',strip=True))
    if listing is None:
        raise ValueError('Fiyat listesi bulunamadi.')
    match = re.search(r'(\d{1,2}) (\w+) (\d{4}).*itibaren geçerli', ' '.join(introduction))
    if not match or match[2].lower() not in MONTHS:
        raise ValueError('Acik gecerlilik tarihi bulunamadi.')
    effective = datetime(int(match[3]),MONTHS[match[2].lower()],int(match[1])).date().isoformat()
    if effective > now.date().isoformat():
        raise ValueError('Gelecekteki liste gozlem olarak alinmadi.')
    rows, seen = [], set()
    for li in listing.find_all('li'):
        # HTML contains unclosed li tags. Exclude descendant li text explicitly.
        text = clean(' '.join(str(t) for t in li.find_all(string=True) if t.find_parent('li') is li))
        match = re.fullmatch(r'(.+?):\s*(.+ TL)',text)
        if not match:
            raise ValueError('Liste satiri yapisi degisti.')
        name, price = match[1], money(match[2])
        if name.casefold() in seen:
            raise ValueError('Tekrarlanan urun satiri.')
        seen.add(name.casefold())
        tobacco = 'Tütün' in name
        reasons = ['gramaj_belirtilmemis' if tobacco else 'paket_ici_adet_belirtilmemis']
        if '/' in name:
            reasons.append('birden_cok_varyant_tek_satirda')
        rows.append(dict(product_name=name,price=price,quantity='',quantity_unit='',currency='TRY',
                         product_type='rolling_tobacco' if tobacco else 'cigarette', collected_at=stamp,
                         source_published_at=dates['datePublished'],source_modified_at=dates['dateModified'],
                         effective_from=effective,effective_until='',source_url=URL,
                         validation_status='historical_source_observation_requires_review',
                         review_reason=';'.join(reasons)))
    if not rows:
        raise ValueError('Liste bos.')
    report = dict(source=URL,collected_at=stamp,source_published_at=dates['datePublished'],
                  source_modified_at=dates['dateModified'],effective_from=effective,effective_until=None,
                  observations=len(rows),ready_for_index=0,grouped_rows=sum('/' in r['product_name'] for r in rows),
                  missing_quantity=len(rows),sha256=hashlib.sha256(html.encode()).hexdigest(),
                  note='Historical announcement, not proof of current prices. Pack size/grams not assumed; grouped variants not expanded.')
    return rows,report

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,default=ROOT/'InflationItems/Datas/02_Alcohol_Tobacco/BirGun/reports')
    args=parser.parse_args(argv)
    with urlopen(Request(URL,headers={'User-Agent':'InflationResearchStudy-price-pilot/1.0'}),timeout=30) as response:
        if response.geturl().rstrip('/') != URL.rstrip('/') or 'text/html' not in response.headers.get('Content-Type',''):
            raise ValueError('Beklenmeyen kaynak yaniti.')
        raw=response.read(5_000_001)
        if len(raw)>5_000_000:
            raise ValueError('Sayfa boyutu beklenenden buyuk.')
    stamp=datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(timespec='microseconds')
    rows,report=parse(raw.decode('utf-8'),stamp)
    args.output_root.mkdir(parents=True,exist_ok=True)
    label=datetime.fromisoformat(stamp).strftime('%Y-%m-%d_%H%M%S_%f')
    target=args.output_root/f'cigarette_news_observations_{label}.csv'
    with target.open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with target.with_suffix('.json').open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)
    print(f'{len(rows)} tarihli kaynak gozlemi; endekse hazir: 0 -> {target}')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
