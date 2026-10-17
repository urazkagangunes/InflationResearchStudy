"""Collect explicitly sized whisky tables as source observations."""
import argparse
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

URL = 'https://alkolfiyatlari.co/viski-fiyatlari/'
ROOT = Path(__file__).resolve().parents[4]
FIELDS = ['product_name', 'price', 'volume_ml', 'packaging', 'currency', 'price_type',
          'collected_at', 'source_published_at', 'source_last_checked_at', 'effective_from',
          'source_url', 'validation_status']
MONTHS = dict(zip(['ocak','şubat','mart','nisan','mayıs','haziran','temmuz','ağustos',
                   'eylül','ekim','kasım','aralık'], range(1,13)))

def clean(text):
    return re.sub(r'\s+', ' ', text).strip()

def money(text):
    value = clean(text)
    if not re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})? TL', value):
        raise ValueError('Tek ve acik TL fiyati degil.')
    result = Decimal(value[:-3].replace('.', '').replace(',', '.'))
    if result <= 0:
        raise ValueError('Pozitif fiyat gerekli.')
    return format(result, '.2f')

def parse(html, stamp):
    now = datetime.fromisoformat(stamp)
    soup = BeautifulSoup(html, 'html.parser')
    h1 = soup.find('h1')
    if not h1 or 'Viski Fiyatları' not in h1.get_text():
        raise ValueError('Beklenen viski sayfasi bulunamadi.')
    times = {t['datetime'] for t in soup.select('time[datetime]')}
    if len(times) != 1:
        raise ValueError('Tek sayfa yayin zamani bulunamadi.')
    published = times.pop()
    if datetime.fromisoformat(published).date() > now.date():
        raise ValueError('Sayfa tarihi gelecekte.')
    check = re.search(r'son olarak (\d{1,2}) (\w+) (\d{4}) tarihinde kontrol edildi',
                      soup.get_text(' ', strip=True), flags=re.I)
    checked = ''
    if check:
        month = MONTHS.get(check[2].lower())
        if not month:
            raise ValueError('Kontrol tarihi ayi taninmadi.')
        checked = datetime(int(check[3]), month, int(check[1])).date().isoformat()
        if checked > now.date().isoformat():
            raise ValueError('Fiyat kontrol tarihi gelecekte.')
    expected = {
        ('Viski (70 cl)', 'Güncel Fiyat'): 'summary',
        ('Marka', '35 cl', '50 cl', '70 cl', '100 cl', '150/175 cl'): 'sizes',
        ('Ürün (70 cl)', 'Güncel Fiyat'): 'premium',
    }
    tables = {}
    for table in soup.select('table'):
        first = table.find('tr')
        headers = tuple(clean(c.get_text(' ',strip=True)) for c in first.find_all(['th','td'])) if first else ()
        if headers not in expected:
            raise ValueError('Beklenmeyen tablo basligi; kaynak kontrol edilmeli.')
        kind = expected[headers]
        if kind in tables:
            raise ValueError('Tablo tekrarlandi.')
        tables[kind] = (table, headers)
    if set(tables) != {'summary', 'sizes', 'premium'}:
        raise ValueError('Beklenen uc fiyat tablosu bulunamadi.')
    observations, rejected = {}, []
    duplicates = 0
    aliases = {'Jameson': 'Jameson Irish Whiskey'}
    for kind, (table, headers) in tables.items():
        table_names = set()
        for tr in table.select('tr')[1:]:
            cells = [clean(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'])]
            if not any(cells):
                continue
            if len(cells) != len(headers):
                raise ValueError('Urun tablosu sutun sayisi degisti.')
            name = aliases.get(cells[0], cells[0])
            if not name or name.casefold() in table_names:
                raise ValueError('Bos veya ayni tabloda tekrarlanan urun.')
            table_names.add(name.casefold())
            values = [(int(headers[i].split()[0]) * 10, cells[i]) for i in range(1,5)] if kind == 'sizes' else [(700,cells[1])]
            if kind == 'sizes' and cells[5] not in ('', '—', '–', '-'):
                rejected.append(dict(product=name, raw_price=cells[5], reason='Belirsiz hacim: 150/175 cl', table=kind))
            for volume, raw in values:
                try:
                    price = money(raw)
                except ValueError as exc:
                    rejected.append(dict(product=name, volume_ml=volume, raw_price=raw, reason=str(exc), table=kind))
                    continue
                key = (name.casefold(), volume)
                if key not in observations:
                    observations[key] = dict(name=name, volume=volume, prices=set(), tables=[])
                item = observations[key]
                if price in item['prices']:
                    duplicates += 1
                item['prices'].add(price)
                item['tables'].append(kind)
    rows = []
    for item in observations.values():
        if len(item['prices']) != 1:
            rejected.append(dict(product=item['name'], volume_ml=item['volume'], prices=sorted(item['prices']),
                                 reason='Ayni urun ve hacim icin celiskili fiyatlar', tables=item['tables']))
            continue
        rows.append(dict(product_name=f"{item['name']} | {item['volume'] // 10} cl | Şişe",
                         price=next(iter(item['prices'])), volume_ml=str(item['volume']),
                         packaging='bottle', currency='TRY', price_type='compiled_recommended_retail',
                         collected_at=stamp, source_published_at=published,
                         source_last_checked_at=checked, effective_from='', source_url=URL,
                         validation_status='source_observation_not_independently_verified'))
    rows.sort(key=lambda row: row['product_name'])
    if not rows:
        raise ValueError('Hicbir gecerli gozlem bulunamadi.')
    report = dict(source=URL, collected_at=stamp, source_published_at=published,
                  source_last_checked_at=checked, effective_from=None, accepted=len(rows),
                  rejected=rejected, duplicates_collapsed=duplicates,
                  scope='Summary, explicit 35/50/70/100 cl and premium 70 cl tables; ambiguous sizes and prose excluded',
                  sha256=hashlib.sha256(html.encode('utf-8')).hexdigest(),
                  note='Source observations only; no independent store-price or effective-date verification.')
    return rows, report
