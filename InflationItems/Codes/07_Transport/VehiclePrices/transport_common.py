"""Shared validation and daily publishing for the additive transport collectors."""
import csv
from datetime import date, datetime
from decimal import Decimal
import os
from pathlib import Path
import re
import tempfile

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from price_csv import FIELDS, classify

def repo_root():
    return Path(__file__).resolve().parents[4]

def profile_dir(source):
    base = Path(os.environ.get('INFLATION_BROWSER_PROFILE_ROOT', repo_root() / '.cache' / 'vehicle_prices'))
    base.mkdir(parents=True, exist_ok=True)
    (base / '.gitignore').write_text('*\n', encoding='utf-8')
    return base / source

def parse_price(text):
    value = re.sub(r'\s+', '', text).replace('TL', '').replace('₺', '')
    if value in ('', '-', '–', '—'):
        return None
    if not re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?', value):
        raise ValueError(f'Taninmayan fiyat: {text!r}')
    result = Decimal(value.replace('.', '').replace(',', '.'))
    if result <= 0:
        raise ValueError(f'Sifir/negatif fiyat: {text!r}')
    return format(result, '.2f')

def daily_path(root, source, day):
    date.fromisoformat(day)
    return Path(root) / source / f'{source.lower()}_{day}.csv'

def publish(root, source, day, rows, replace=False):
    target = daily_path(root, source, day)
    if not rows:
        raise ValueError('Bos veri yayinlanamaz.')
    seen = set()
    for row in rows:
        name = re.sub(r'\s+', ' ', row.get('product_name', '')).strip().lower()
        if not name or name in seen:
            raise ValueError('Bos veya tekrar eden urun adi.')
        seen.add(name)
        for field in ('price', 'campaign_price'):
            value = row.get(field, '')
            if field == 'campaign_price' and not value:
                continue
            if not re.fullmatch(r'\d+\.\d{2}', str(value)) or Decimal(value) <= 0:
                raise ValueError(f'Gecersiz {field}: {value}')
        if row.get('collected_at', '')[:10] != day:
            raise ValueError('Toplama tarihi dosya tarihiyle uyusmuyor.')
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.parent / '.publish.lock'
    with lock.open('x'):
        pass
    try:
        existing = [p for p in target.parent.rglob(f'*{day}*.csv')
                    if not any(x in {'archive', 'reports', 'output', 'InflationData'}
                               for x in p.relative_to(target.parent).parts[:-1])]
        if existing and not replace:
            raise FileExistsError(f'Bu gunun verisi var: {existing[0]}')
        fd, tmp = tempfile.mkstemp(prefix='.prices-', suffix='.tmp', dir=target.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows({'product_name': row['product_name'], 'price': row['price'], 'category_number': 7, 'sub_category_number': classify(row, source, 7)} for row in rows)
            os.replace(tmp, target)
            for old in existing:
                if old != target:
                    old.unlink()
        finally:
            Path(tmp).unlink(missing_ok=True)
    finally:
        lock.unlink(missing_ok=True)
    return target
