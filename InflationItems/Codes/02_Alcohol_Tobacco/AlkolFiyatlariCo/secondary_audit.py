"""Audit secondary sources without publishing their prices as index inputs."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from whisky_pilot import ROOT,clean,money

SOURCES={
 'wowturkey':'https://www.wowturkey.com/konu/guncel-zamli-sigara-fiyatlari-agustos-2026.13949/',
 'enucuz':'https://enucuzfiyatlari.com/en-ucuz-bira/'}

def wow_audit(html):
    soup=BeautifulSoup(html,'html.parser')
    body=soup.select_one('article.message--post .bbWrapper')
    if body is None:raise ValueError('Ilk forum gonderisi bulunamadi.')
    post=body.find_parent('article',class_='message--post')
    dates=list(dict.fromkeys(t['datetime'] for t in post.select('time[datetime]')))
    tables=[]
    for table in body.select('table'):
        trs=table.select('tr')
        headers=[clean(c.get_text(' ',strip=True)) for c in trs[0].find_all(['th','td'])]
        if headers not in (['Marka / Ürün','Güncel Fiyat (TL)'],['Marka','Fiyat (TL)']):
            raise ValueError('Forum tablo basligi degisti.')
        records={}
        for tr in trs[1:]:
            cells=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'])]
            if len(cells)!=2:raise ValueError('Forum tablo satiri degisti.')
            if cells[0] in records:raise ValueError('Forum tablosunda tekrar.')
            records[cells[0]]=money(cells[1])
        tables.append(records)
    if len(tables)!=2:raise ValueError('Iki forum fiyat tablosu bekleniyordu.')
    bullets={}
    for li in body.select('li'):
        text=clean(li.get_text(' ',strip=True))
        match=re.fullmatch(r'(.+?):\s*(.+ TL)',text)
        if not match:raise ValueError('Forum liste satiri degisti.')
        if match[1] in bullets:raise ValueError('Forum maddesi tekrarlandi.')
        bullets[match[1]]=money(match[2])
    # Compare only explicit labels; keep grouped labels in the evidence.
    pairs=[('CAMEL Slender / Deep Blue','Camel Slender'),
           ('CAMEL Slender / Deep Blue','Camel Deep Blue'),
           ('CAMEL Black & White','Camel Black & White'),
           ('CAMEL Yellow & Brown','Camel Yellow & Brown')]
    conflicts=[]
    for group,single in pairs:
        if group in bullets and single in tables[1] and bullets[group]!=tables[1][single]:
            conflicts.append(dict(product=single,main_label=group,main_price=bullets[group],
                                  comparison_price=tables[1][single]))
    return dict(post_dates=dates,table_rows=sum(map(len,tables)),bullet_rows=len(bullets),
                tested_internal_conflicts=conflicts,scope='First post only; replies excluded.',
                decision='review_only',ready_for_index=0,
                reason='Quantity/effective-date evidence requires review; tested conflicts are listed separately.')

def enucuz_audit(html):
    soup=BeautifulSoup(html,'html.parser')
    article=soup.find('article')
    if article is None or not article.h1:raise ValueError('Yazi bulunamadi.')
    title=clean(article.h1.get_text(' ',strip=True))
    if 'Bira Fiyatları' not in title:raise ValueError('Bira sayfasi bekleniyordu.')
    visible=re.search(r'Güncellendi:\s*(\d{1,2}\s+\w+\s+\d{4})',article.get_text(' ',strip=True))
    if not visible:raise ValueError('Gorunur guncelleme tarihi bulunamadi.')
    meta={m['property']:m.get('content','') for m in soup.select('meta[property^="article:"]')}
    rows={};duplicates=0;count=0
    for table in article.select('table'):
        count+=1
        trs=table.select('tr')
        headers=[clean(c.get_text(' ',strip=True)) for c in trs[0].find_all(['th','td'])]
        if headers!=['Sıra','Bira Markası','Ambalaj Türü','Fiyat (TL)']:raise ValueError('Bira tablo basligi degisti.')
        for tr in trs[1:]:
            cells=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'])]
            if len(cells)!=4:raise ValueError('Bira tablo satiri degisti.')
            key=(cells[1].replace('’', "'").casefold(),cells[2].casefold());price=money(cells[3])
            if key in rows:
                if rows[key]!=price:raise ValueError('Tekrarlanan tablolar celisiyor.')
                duplicates+=1
            rows[key]=price
    if count!=2 or not rows:raise ValueError('Iki fiyat tablosu bekleniyordu.')
    return dict(title=title,visible_updated=visible[1],metadata_published=meta.get('article:published_time'),
                metadata_modified=meta.get('article:modified_time'),unique_rows=len(rows),duplicates_collapsed=duplicates,
                body_mentions_2024='2024 yılı itibarıyla' in article.get_text(' ',strip=True),
                decision='review_only',ready_for_index=0,
                reason='Title/body year and visible/metadata update dates require reconciliation; current validity unverified.')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,default=ROOT/'secondary-source-reports')
    args=parser.parse_args(argv)
    report={'collected_at':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(timespec='microseconds'),'sources':{}}
    for name,url in SOURCES.items():
        with urlopen(Request(url,headers={'User-Agent':'InflationResearchStudy-price-pilot/1.0'}),timeout=30) as response:
            if response.geturl().rstrip('/')!=url.rstrip('/') or 'text/html' not in response.headers.get('Content-Type',''):raise ValueError('Beklenmeyen yanit.')
            raw=response.read(5_000_001)
            if len(raw)>5_000_000:raise ValueError('Sayfa fazla buyuk.')
        audit=wow_audit(raw.decode('utf-8')) if name=='wowturkey' else enucuz_audit(raw.decode('utf-8'))
        audit.update(source_url=url,sha256=hashlib.sha256(raw).hexdigest())
        report['sources'][name]=audit
    args.output_root.mkdir(parents=True,exist_ok=True)
    label=datetime.fromisoformat(report['collected_at']).strftime('%Y-%m-%d_%H%M%S_%f')
    target=args.output_root/f'secondary_audit_{label}.json'
    with target.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(f'2 kaynak kontrol edildi; endekse aktarim yok -> {target}')
    return 0
