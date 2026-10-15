"""Explicit-size raki and vodka table observations."""
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
from whisky_pilot import ROOT, FIELDS, clean, money

SIZES=('35 cl','50 cl','70 cl','100 cl')
CONFIG={
    'raki': {'title':'Rakı Fiyatları','tables': {
        ('Rakı Markası',*SIZES):'matrix',
        ('Yeni Rakı Serisi',*SIZES,'150 cl'):'matrix'}},
    'votka': {'title':'Votka Fiyatları','tables': {
        ('Votka Markası',*SIZES):'matrix',
        ('Premium Votka (70 cl)','Güncel Fiyat'):'premium',
        ('Absolut Vodka',*SIZES):'unspecified_variant'}}}

def parse(html,stamp,kind):
    cfg=CONFIG[kind]
    now=datetime.fromisoformat(stamp)
    soup=BeautifulSoup(html,'html.parser')
    if not soup.h1 or cfg['title'] not in soup.h1.get_text():
        raise ValueError('Beklenen kategori sayfasi degil.')
    times={t['datetime'] for t in soup.select('time[datetime]')}
    if len(times)!=1:
        raise ValueError('Tek yayin zamani bulunamadi.')
    published=times.pop()
    date=datetime.fromisoformat(published)
    if date.tzinfo is None or date>now:
        raise ValueError('Yayin zamani gecersiz veya gelecekte.')
    found=set();items={};review=[];missing=[];duplicates=0
    for table in soup.select('table'):
        trs=table.select('tr')
        headers=tuple(clean(c.get_text(' ',strip=True)) for c in trs[0].find_all(['th','td'])) if trs else ()
        mode=cfg['tables'].get(headers)
        if mode is None or headers in found:
            raise ValueError('Tablo basligi degisti veya tekrarlandi.')
        found.add(headers)
        seen=set()
        for tr in trs[1:]:
            cells=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'])]
            if not any(cells):continue
            if len(cells)!=len(headers):raise ValueError('Sutun sayisi degisti.')
            name=cells[0]
            if not name or name.casefold() in seen:raise ValueError('Urun adi bos veya tekrarlandi.')
            seen.add(name.casefold())
            if mode=='unspecified_variant':
                for i,raw in enumerate(cells[1:],1):
                    review.append(dict(product=headers[0],volume=headers[i],raw_price=raw,
                                       reason='Seri belirtilmemis; Absolut Blue ile esit oldugu varsayilmadi.'))
                continue
            name={'Yeni Rakı (Yeni Seri)':'Yeni Rakı Yeni Seri'}.get(name,name)
            explicit=re.search(r'\((\d+) cl\)$',name)
            if explicit:name=clean(name[:explicit.start()])
            for i,raw in enumerate(cells[1:],1):
                volume=700 if mode=='premium' else int(headers[i].split()[0])*10
                if raw in ('','—','–','-'):
                    missing.append(dict(product=name,volume_ml=volume,reason='Kaynak hucre bos.'))
                    continue
                if explicit and volume!=int(explicit[1])*10:
                    review.append(dict(product=name,volume_ml=volume,raw_price=raw,reason='Urun adi ve sutun hacmi uyusmuyor.'))
                    continue
                try:price=money(raw)
                except ValueError as exc:
                    review.append(dict(product=name,volume_ml=volume,raw_price=raw,reason=str(exc)))
                    continue
                key=(name.casefold(),volume)
                if key not in items:items[key]=dict(name=name,volume=volume,prices=set())
                item=items[key]
                if price in item['prices']:duplicates+=1
                item['prices'].add(price)
    if found!=set(cfg['tables']):raise ValueError('Beklenen tablolar eksik.')
    rows=[]
    url=f'https://alkolfiyatlari.co/{kind}-fiyatlari/'
    for item in items.values():
        if len(item['prices'])!=1:
            review.append(dict(product=item['name'],volume_ml=item['volume'],prices=sorted(item['prices']),reason='Celiskili fiyatlar.'))
            continue
        rows.append(dict(product_name=f"{item['name']} | {item['volume']//10} cl | Şişe",
                         price=next(iter(item['prices'])),volume_ml=str(item['volume']),packaging='bottle',
                         currency='TRY',price_type='compiled_recommended_retail',collected_at=stamp,
                         source_published_at=published,source_last_checked_at='',effective_from='',source_url=url,
                         validation_status='source_observation_not_independently_verified'))
    if not rows:raise ValueError('Gecerli gozlem yok.')
    rows.sort(key=lambda r:r['product_name'])
    report=dict(source=url,collected_at=stamp,source_published_at=published,source_last_checked_at=None,
                effective_from=None,accepted=len(rows),duplicates_collapsed=duplicates,review=review,missing=missing,
                sha256=hashlib.sha256(html.encode()).hexdigest(),
                note='Compiled source observations. No independently verified current store price or effective date.')
    return rows,report

def main(kind,argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,default=ROOT/'InflationItems/Datas/02_Alcohol_Tobacco/AlkolFiyatlariCo/reports')
    args=parser.parse_args(argv)
    url=f'https://alkolfiyatlari.co/{kind}-fiyatlari/'
    with urlopen(Request(url,headers={'User-Agent':'InflationResearchStudy-price-pilot/1.0'}),timeout=30) as response:
        if response.geturl().rstrip('/')!=url.rstrip('/') or 'text/html' not in response.headers.get('Content-Type',''):
            raise ValueError('Beklenmeyen kaynak yaniti.')
        raw=response.read(5_000_001)
        if len(raw)>5_000_000:raise ValueError('Sayfa fazla buyuk.')
    stamp=datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(timespec='microseconds')
    rows,report=parse(raw.decode('utf-8'),stamp,kind)
    args.output_root.mkdir(parents=True,exist_ok=True)
    label=datetime.fromisoformat(stamp).strftime('%Y-%m-%d_%H%M%S_%f')
    target=args.output_root/f'{kind}_observations_{label}.csv'
    with target.open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    with target.with_suffix('.json').open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)
    print(f'{kind}: {len(rows)} gozlem; {len(report["review"])} inceleme; {len(report["missing"])} bos hucre -> {target}')
    return 0
