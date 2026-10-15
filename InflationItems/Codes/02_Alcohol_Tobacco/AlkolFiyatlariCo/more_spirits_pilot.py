"""Gin, tequila and liqueur source tables; foreign/bar comparisons excluded."""
import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from whisky_pilot import ROOT,FIELDS,clean,money
from beer_wine_pilot import volume

SIZES=('35 cl','50 cl','70 cl','100 cl')
OLD=('Önceki Fiyat','Ekim 2026 Fiyatı')
CONFIG={
 'cin':dict(title='Cin Fiyatları',tables={
  ('Cin Markası',*SIZES):('matrix',1),('Cin (70 cl)','Güncel Fiyat'):('fixed70',1),
  ('Premium Cin','Hacim','Güncel Fiyat'):('explicit',1),
  ('Mekân Tipi','Cin & Tonik Fiyatı'):('skip',1),('Şehir','Ortalama Cin & Tonik Fiyatı'):('skip',1)}),
 'tekila':dict(title='Tekila Fiyatları',tables={
  ('Tekila (70 cl)','Güncel Fiyat'):('fixed70',1),('Olmeca','Hacim','Güncel Fiyat'):('explicit',1),
  ('Ürün','Hacim','Güncel Fiyat'):('explicit',1),('Premium Tekila (70 cl)','Güncel Fiyat'):('fixed70',1),
  ('Ülke','Ortalama Tekila Fiyatı (70 cl)'):('skip',1)}),
 'likor':dict(title='Likör Fiyatları',tables={
  ('Likör','Hacim',*OLD):('monthly',1),('Meyve Likörü (100 cl)',*OLD):('unidentified',1),
  ('Hare Likör','Hacim',*OLD):('monthly',1),('Nazen Likör (35 cl)',*OLD):('fixed35month',1),
  ('Klasik Likör (100 cl)',*OLD):('unidentified',1),('Keglevich Likör','Hacim',*OLD):('monthly',1),
  ('Jägermeister',*OLD):('namevolume',1),('Ürün','Hacim',*OLD):('monthly',2),
  ('Sambuca (70 cl)',*OLD):('fixed70month',1),('Diğer İthal / Özel Seri','Hacim',*OLD):('monthly',1)})}
ALIASES={'Nazen Likör Vişne':'Nazen Vişne Likörü','Nazen Likör Nane':'Nazen Nane Likörü'}

def parse(html,stamp,kind):
    now=datetime.fromisoformat(stamp);cfg=CONFIG[kind]
    soup=BeautifulSoup(html,'html.parser')
    if not soup.h1 or cfg['title'] not in soup.h1.get_text():raise ValueError('Kategori basligi uyusmuyor.')
    dates={t['datetime'] for t in soup.select('time[datetime]')}
    if len(dates)!=1:raise ValueError('Tek yayin tarihi yok.')
    published=dates.pop();pub=datetime.fromisoformat(published)
    if pub.tzinfo is None or pub>now:raise ValueError('Gecersiz yayin tarihi.')
    expected=Counter({h:v[1] for h,v in cfg['tables'].items()});found=Counter()
    items={};review=[];skipped=[];duplicates=0
    for index,table in enumerate(soup.select('table')):
        trs=table.select('tr');headers=tuple(clean(c.get_text(' ',strip=True)) for c in trs[0].find_all(['th','td'])) if trs else ()
        found[headers]+=1
        if headers not in expected or found[headers]>expected[headers]:raise ValueError('Tablo basliklari degisti.')
        mode=cfg['tables'][headers][0]
        if mode=='skip':
            skipped.append(dict(table=index,rows=len(trs)-1,reason='Bar/kokteyl veya yurtdisi fiyat karsilastirmasi.'))
            continue
        for tr in trs[1:]:
            cells=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'])]
            if not any(cells):continue
            if len(cells)!=len(headers):raise ValueError('Sutun sayisi degisti.')
            original=cells[0];name=ALIASES.get(original,original) if kind=='likor' else original
            try:
                if not name:raise ValueError('Urun adi bos.')
                if '/' in name:raise ValueError('Birden cok cesit ayni satirda.')
                if mode=='unidentified':raise ValueError('Uretici/seri belirsiz veya satir hacmi tabloyla celisiyor.')
                if kind=='likor' and name in ('Captain Morgan Gold','Captain Morgan White','Zacapa'):
                    raise ValueError('Rom; likor kategorisine otomatik dahil edilmedi.')
                period='2026-10' if mode in ('monthly','fixed35month','fixed70month','namevolume') else ''
                if period and period>now.strftime('%Y-%m'):raise ValueError('Gelecek donem fiyati.')
                if mode=='matrix':values=[(volume(headers[i]),cells[i]) for i in range(1,len(headers))]
                elif mode in ('fixed70','fixed70month','fixed35month'):
                    values=[(350 if mode=='fixed35month' else 700,cells[-1])]
                elif mode in ('explicit','monthly'):values=[(volume(cells[1]),cells[-1])]
                else:
                    size=volume(name)
                    name=clean(re.sub(r'^\d+(?:[.,]\d+)?\s*cl\s+','',name))
                    values=[(size,cells[-1])]
            except ValueError as exc:
                review.append(dict(table=index,product=original,raw_cells=cells,reason=str(exc)));continue
            for size,raw in values:
                try:price=money(raw)
                except ValueError as exc:
                    review.append(dict(table=index,product=original,volume_ml=size,raw_price=raw,reason=str(exc)));continue
                key=(name.casefold(),size)
                if key not in items:items[key]=dict(name=name,size=size,prices=set(),tables=[],period=period)
                item=items[key]
                if price in item['prices']:duplicates+=1
                item['prices'].add(price);item['tables'].append(index)
    if found!=expected:raise ValueError('Beklenen tablolar eksik.')
    rows=[];url=f'https://alkolfiyatlari.co/{kind}-fiyatlari/'
    for item in items.values():
        if len(item['prices'])!=1:
            review.append(dict(product=item['name'],volume_ml=item['size'],prices=sorted(item['prices']),tables=item['tables'],reason='Ayni urun/hacim icin celiskili fiyatlar.'))
            continue
        rows.append(dict(product_name=f"{item['name']} | {item['size']//10} cl | Şişe",price=next(iter(item['prices'])),
                         volume_ml=str(item['size']),packaging='bottle',currency='TRY',price_type='compiled_source_list_price',
                         collected_at=stamp,source_published_at=published,source_last_checked_at='',effective_from='',
                         source_url=url,validation_status='source_observation_not_independently_verified',
                         price_period=item['period'],source_table=','.join(map(str,item['tables']))))
    if not rows:raise ValueError('Gecerli gozlem yok.')
    rows.sort(key=lambda r:r['product_name'])
    report=dict(source=url,collected_at=stamp,source_published_at=published,accepted=len(rows),review=review,
                duplicates_collapsed=duplicates,skipped_tables=skipped,sha256=hashlib.sha256(html.encode()).hexdigest(),
                note='Source observations only; unknown series, grouped variants and conflicts excluded. Current store prices not independently verified.')
    return rows,report

def main(kind,argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,default=ROOT/'InflationItems/Datas/02_Alcohol_Tobacco/AlkolFiyatlariCo/reports')
    args=parser.parse_args(argv);url=f'https://alkolfiyatlari.co/{kind}-fiyatlari/'
    with urlopen(Request(url,headers={'User-Agent':'InflationResearchStudy-price-pilot/1.0'}),timeout=30) as response:
        if response.geturl().rstrip('/')!=url.rstrip('/') or 'text/html' not in response.headers.get('Content-Type',''):raise ValueError('Beklenmeyen yanit.')
        raw=response.read(5_000_001)
        if len(raw)>5_000_000:raise ValueError('Sayfa fazla buyuk.')
    stamp=datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(timespec='microseconds')
    rows,report=parse(raw.decode('utf-8'),stamp,kind)
    args.output_root.mkdir(parents=True,exist_ok=True)
    target=args.output_root/f'{kind}_observations_{datetime.fromisoformat(stamp).strftime("%Y-%m-%d_%H%M%S_%f")}.csv'
    with target.open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS+['price_period','source_table']);writer.writeheader();writer.writerows(rows)
    with target.with_suffix('.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(f'{kind}: {len(rows)} gozlem; {len(report["review"])} inceleme -> {target}')
    return 0
