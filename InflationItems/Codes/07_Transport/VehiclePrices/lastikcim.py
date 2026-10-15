"""Lastikcim sabit baslangic orneklemi; tum katalog taramasi degildir."""
from datetime import datetime
import json
from pathlib import Path
import re
from urllib.parse import urlparse,parse_qs
from zoneinfo import ZoneInfo
from transport_common import parse_price

ROOT=Path(__file__).resolve().parent


def identity(item,name):
    parsed=urlparse(item['url'])
    if parsed.scheme!='https' or parsed.hostname!='www.lastikcim.com.tr':
        raise ValueError('Urun listesinde beklenmeyen kaynak adresi.')
    product_id=parsed.path.rsplit(',',1)[-1]
    if not re.fullmatch(r'\d+-[A-Za-z0-9-]+',product_id):
        raise ValueError(f'Urun kodu okunamadi: {name}')
    year=parse_qs(parsed.query).get('dot',[''])[0]
    if item['category']=='lastik' and not re.fullmatch(r'20\d{2}',year):
        raise ValueError(f'{name}: lastik uretim yili sabitlenmemis.')
    return f"Lastikcim {name} | {item['category']}"+(f' | Uretim {year}' if year else '')+f' | {product_id}'


def collect(headed=False):
    from playwright.sync_api import sync_playwright, Error as BrowserError
    items=json.loads((ROOT/'lastikcim_urun_listesi.json').read_text(encoding='utf-8'))
    if not items or len({i['url'] for i in items})!=len(items):
        raise ValueError('Sabit urun listesi bos veya tekrarlanan adresler var.')
    now=datetime.now(ZoneInfo('Europe/Istanbul'))
    records=[]
    unavailable=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=not headed)
        try:
            page=browser.new_page(locale='tr-TR',timezone_id='Europe/Istanbul')
            page.goto('https://www.lastikcim.com.tr/',wait_until='networkidle',timeout=45000)
            for n,item in enumerate(items,1):
                identity(item,item['name'])
                print(f"[{n}/{len(items)}] {item['name']}",flush=True)
                for attempt in range(2):
                    try:
                        page.goto(item['url'],wait_until='domcontentloaded',timeout=45000)
                        break
                    except BrowserError as exc:
                        if attempt or 'ERR_NETWORK_CHANGED' not in str(exc):
                            raise
                        print('Gecici ag degisikligi; ayni adres yeniden deneniyor.',flush=True)
                page.locator('h1').first.wait_for(state='attached',timeout=20000)
                name=re.sub(r'\s+',' ',page.locator('h1').first.inner_text()).strip()
                if name!=item['name']:
                    raise ValueError(f"Urun adi degisti: {item['name']} -> {name}")
                if page.get_by_text('GELİNCE HABER VER',exact=True).count():
                    unavailable.append(dict(product_name=name,source_url=page.url,reason='Stokta yok; satis fiyati yayimlanmiyor'))
                    print('Stokta yok: fiyat CSVsine eklenmedi.',flush=True)
                    continue
                page.locator('div.sc-i5n8xm-10').first.wait_for(state='attached',timeout=15000)
                discounted=page.locator('div.sc-i5n8xm-10 strong.sc-i5n8xm-9')
                prices=discounted if discounted.count() else page.locator('div.sc-i5n8xm-10 span.sc-i5n8xm-11')
                if prices.count()!=1:
                    raise ValueError(f'{name}: tek satis fiyati okunamadi.')
                price=parse_price(prices.inner_text())
                if not price:
                    raise ValueError(f'{name}: satis fiyati bos.')
                expected_year=parse_qs(urlparse(item['url']).query).get('dot')
                if expected_year and parse_qs(urlparse(page.url).query).get('dot')!=expected_year:
                    raise ValueError(f'{name}: lastik uretim yili adresi degisti.')
                records.append(dict(product_name=identity(item,name),price=price,campaign_price='',model_year='',
                    collected_at=datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(timespec='seconds'),
                    price_type='live_product_current',price_label='Urun sayfasinda gorunen satis fiyati; sepet indirimi haric',source_url=page.url))
        finally:browser.close()
    if not records:
        raise ValueError('Satis fiyati olan urun kalmadi.')
    return records,now,unavailable,len(items)
