"""Beer/wine observations preserving size, packaging and deposit distinctions."""
import argparse
from collections import Counter
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from whisky_pilot import ROOT,FIELDS,clean,money

EXTRA=['deposit_status','deposit_amount','price_period','source_table']
BEER=('Ürün','Ambalaj','Güncel Fiyat')
SPECIAL=('Ürün','Hacim / Ambalaj','Güncel Fiyat')
COMPARE=('Ürün','Hacim','Fiyat','Litre Fiyatı')
WINE=('Şarap (75 cl)','Tür','Güncel Fiyat')
RED=('Kırmızı Şarap','Güncel Fiyat')
MONTHLY=('Ürün','Hacim','Önceki Fiyat','Ekim 2026 Fiyatı')

def volume(text):
    hits=re.findall(r'(?<![\d.,])(\d+(?:[.,]\d+)?)\s*cl\b',text,flags=re.I)
    if len(hits)!=1:raise ValueError('Tek acik hacim yok.')
    value=Decimal(hits[0].replace(',','.'))*10
    if value<=0 or value!=int(value):raise ValueError('Gecersiz hacim.')
    return int(value)

def parse(html,stamp,kind):
    now=datetime.fromisoformat(stamp)
    soup=BeautifulSoup(html,'html.parser')
    title='Bira Fiyatları' if kind=='bira' else 'Şarap Fiyatları'
    if not soup.h1 or title not in soup.h1.get_text():raise ValueError('Beklenen kategori degil.')
    times={t['datetime'] for t in soup.select('time[datetime]')}
    if len(times)!=1:raise ValueError('Tek yayin zamani bulunamadi.')
    published=times.pop();pub=datetime.fromisoformat(published)
    if pub.tzinfo is None or pub>now:raise ValueError('Gecersiz yayin tarihi.')
    expected=Counter({BEER:3,COMPARE:1,SPECIAL:1}) if kind=='bira' else Counter({WINE:1,RED:1,COMPARE:1,MONTHLY:2})
    found=Counter();items={};review=[];skipped=[];duplicates=0
    aliases={'Kırmızı Tuborg (Tuborg Special)':'Tuborg Special','Kırmızı Tuborg Shot Special':'Tuborg Shot Special'}
    for index,table in enumerate(soup.select('table')):
        trs=table.select('tr')
        heads=tuple(clean(c.get_text(' ',strip=True)) for c in trs[0].find_all(['th','td'])) if trs else ()
        found[heads]+=1
        if heads not in expected or found[heads]>expected[heads]:raise ValueError('Tablo basligi veya sayisi degisti.')
        if heads==COMPARE and kind=='bira':
            skipped.append(dict(table=index,reason='Karsilastirma tekrari; litre fiyatlari alinmadi.',rows=len(trs)-1))
            continue
        for tr in trs[1:]:
            cells=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'])]
            if not any(cells):continue
            if len(cells)!=len(heads):raise ValueError('Sutun sayisi degisti.')
            original=cells[0]
            name=aliases.get(original,original) if kind=='bira' else original
            try:
                if not name:raise ValueError('Urun adi bos.')
                # A slash in a wine blend (e.g. Cabernet/Syrah) can describe one product;
                # only explicitly sized, individual names reach acceptance here.
                if kind=='bira':
                    package=cells[1]
                    if '/' in name or '/' in package:raise ValueError('Birden cok varyant veya ambalaj.')
                    size=volume(package)
                    packaging='can' if 'kutu' in package.lower() else 'bottle' if 'şişe' in package.lower() else ''
                    if not packaging:raise ValueError('Ambalaj belirsiz.')
                    deposit='non_returnable' if 'depozitosuz' in package else 'returnable_amount_unknown' if 'depozitolu' in package else 'unspecified'
                    raw=cells[2];period=''
                else:
                    if heads==WINE:
                        if '/' in name or 'Şarapları' in name:raise ValueError('Birden cok seri veya cesit.')
                        size=750;raw=cells[2];period=''
                    elif heads==RED:
                        size=volume(name)
                        raw=cells[1];period=''
                        name=clean(re.sub(r'\(\d+(?:[.,]\d+)?\s*cl\)','',name))
                    else:
                        if '/' in name:raise ValueError('Birden cok cesit.')
                        size=volume(cells[1])
                        raw=cells[3] if heads==MONTHLY else cells[2]
                        period='2026-10' if heads==MONTHLY else ''
                        if period and period>now.strftime('%Y-%m'):raise ValueError('Gelecek donem fiyati.')
                    packaging='bottle';deposit='unspecified'
                price=money(raw)
            except ValueError as exc:
                review.append(dict(table=index,product=original,raw_cells=cells,reason=str(exc)))
                continue
            key=(name.casefold(),size,packaging,deposit)
            if key not in items:items[key]=dict(name=name,size=size,packaging=packaging,deposit=deposit,prices=set(),periods=set(),tables=[])
            item=items[key]
            if price in item['prices']:duplicates+=1
            item['prices'].add(price);item['periods'].add(period);item['tables'].append(index)
    if found!=expected:raise ValueError('Beklenen tablolar eksik.')
    rows=[];url=f'https://alkolfiyatlari.co/{kind}-fiyatlari/'
    for item in items.values():
        if len(item['prices'])!=1:
            review.append(dict(product=item['name'],volume_ml=item['size'],prices=sorted(item['prices']),reason='Celiskili fiyatlar.'))
            continue
        cl=format(Decimal(item['size'])/10,'f').rstrip('0').rstrip('.') if item['size']%10 else str(item['size']//10)
        pack='Kutu' if item['packaging']=='can' else 'Şişe'
        name=f"{item['name']} | {cl} cl | {pack}"
        if kind=='bira':name+=f" | {item['deposit']}"
        rows.append(dict(product_name=name,price=next(iter(item['prices'])),volume_ml=str(item['size']),
                         packaging=item['packaging'],currency='TRY',price_type='compiled_source_list_price_deposit_basis_unverified',
                         collected_at=stamp,source_published_at=published,source_last_checked_at='',effective_from='',
                         source_url=url,validation_status='source_observation_not_independently_verified',
                         deposit_status=item['deposit'],deposit_amount='',price_period=';'.join(sorted(p for p in item['periods'] if p)),
                         source_table=','.join(map(str,item['tables']))))
    if not rows:raise ValueError('Gecerli gozlem yok.')
    rows.sort(key=lambda row:row['product_name'])
    report=dict(source=url,collected_at=stamp,source_published_at=published,accepted=len(rows),review=review,
                skipped_tables=skipped,duplicates_collapsed=duplicates,sha256=hashlib.sha256(html.encode()).hexdigest(),
                note='Listed product prices only. Deposit amount/basis and current store validity not independently verified; old prices and litre-price columns not collected.')
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
        writer=csv.DictWriter(stream,fieldnames=FIELDS+EXTRA);writer.writeheader();writer.writerows(rows)
    with target.with_suffix('.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(f'{kind}: {len(rows)} gozlem; {len(report["review"])} inceleme -> {target}')
    return 0
