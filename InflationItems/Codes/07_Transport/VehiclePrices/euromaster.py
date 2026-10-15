"""Euromaster KDV dahil tavsiye edilen iscilik tarifesi."""
from datetime import datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from transport_common import parse_price

URL='https://www.euromaster.com.tr/iscilik-fiyatlari'


def parse_table(html,stamp):
    soup=BeautifulSoup(html,'html.parser')
    tables=[t for t in soup.select('table') if 'TAVSİYE EDİLEN KDV DAHİL İŞÇİLİK FİYAT LİSTESİ' in t.get_text(' ',strip=True)]
    if len(tables)!=1:raise ValueError('Tek iscilik fiyat tablosu bulunamadi.')
    records=[];missing=[];groups=[];group=None
    for tr in tables[0].select('tr'):
        cells=tr.find_all(['th','td'],recursive=False)
        values=[re.sub(r'\s+',' ',c.get_text(' ',strip=True)).strip() for c in cells]
        if not any(values):continue
        if len(cells)==1 and cells[0].get('colspan')=='2':
            group=values[0]
            if not group:raise ValueError('Hizmet grubu basligi bos.')
            groups.append(group)
            continue
        if len(values)==2 and values[0]=='TAVSİYE EDİLEN KDV DAHİL İŞÇİLİK FİYAT LİSTESİ':continue
        if len(values)!=2 or not group or not values[0]:raise ValueError('Hizmet satiri yapisi degisti.')
        name,raw_price=values
        price=parse_price(raw_price)
        if price is None:
            missing.append(dict(service=name,group=group,reason='Resmi tabloda fiyat bos'))
            continue
        records.append(dict(product_name=f'Euromaster {group} | {name}',price=price,campaign_price='',
                            model_year='',collected_at=stamp,price_type='recommended_service_vat_included',
                            price_label='Tavsiye edilen KDV dahil iscilik fiyati; * iscilik, ** iscilik + malzeme',source_url=URL))
    if len(groups)!=5 or not records or len({r['product_name'] for r in records})!=len(records):
        raise ValueError('Beklenen 5 grup okunamadi veya tekrarlanan hizmet var; kontrol edilmeli.')
    return sorted(records,key=lambda r:r['product_name']),missing,groups


def collect(headed=False):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=not headed)
        try:
            page=browser.new_page(locale='tr-TR',timezone_id='Europe/Istanbul')
            page.goto(URL,wait_until='networkidle',timeout=60000)
            page.locator('table.table-striped').wait_for(state='attached',timeout=30000)
            now=datetime.now(ZoneInfo('Europe/Istanbul'))
            rows,missing,groups=parse_table(page.content(),now.isoformat(timespec='seconds'))
        finally:browser.close()
    return rows,missing,groups,now
