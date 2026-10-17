"""Run independent collectors and write repo-compatible daily CSVs."""
import argparse
from datetime import datetime
import importlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from transport_common import daily_path, publish, repo_root

SOURCES = dict(Toyota='toyota', Renault='renault', Hyundai='hyundai', Honda='honda',
               Mondial='mondial', Decathlon='decathlon_live', Salcano='salcano',
               Lastikcim='lastikcim', Euromaster='euromaster')
INTERACTIVE = {'Decathlon', 'Salcano'}

def main(argv=None):
    parser = argparse.ArgumentParser(description='Ulastirma fiyatlarini repo CSV duzeninde toplar.')
    parser.add_argument('--sources', nargs='+', choices=SOURCES, default=list(SOURCES))
    parser.add_argument('--list-sources', action='store_true')
    parser.add_argument('--non-interactive', action='store_true', help='Decathlon ve Salcano atlanir.')
    parser.add_argument('--replace-day', action='store_true', help='Ayni gunun CSV dosyasini yenile.')
    parser.add_argument('--headed', action='store_true', help='Diger kaynaklarda da tarayiciyi goster.')
    parser.add_argument('--data-root', type=Path, default=repo_root() / 'InflationItems/Datas/07_Transport/motor_bicyle_car')
    args = parser.parse_args(argv)
    if args.list_sources:
        for name in SOURCES:
            print(name + (' (gorunur tarayici)' if name in INTERACTIVE else ''))
        return 0
    failed = False
    for name in dict.fromkeys(args.sources):
        if args.non_interactive and name in INTERACTIVE:
            print(f'{name}: gorunur tarayici gerektirdigi icin atlandi.')
            continue
        today = datetime.now(ZoneInfo('Europe/Istanbul')).date().isoformat()
        target = daily_path(args.data_root, name, today)
        if target.exists() and not args.replace_day:
            print(f'{name}: bugunun verisi zaten var, atlandi: {target}')
            continue
        # Exclusive source lock also protects persistent browser profiles.
        target.parent.mkdir(parents=True, exist_ok=True)
        lock = target.parent / '.collect.lock'
        acquired = False
        try:
            with lock.open('x'):
                acquired = True
                module = importlib.import_module(SOURCES[name])
                kwargs = {} if name == 'Decathlon' else ({'hidden': False} if name == 'Salcano' else {'headed': args.headed})
                result = module.collect(**kwargs)
                rows = result[0]
                day = rows[0]['collected_at'][:10] if rows else today
                output = publish(args.data_root, name, day, rows, replace=args.replace_day)
                print(f'{name}: {len(rows)} fiyat -> {output}')
        except Exception as exc:
            failed = True
            print(f'{name}: HATA: {exc}')
        finally:
            if acquired:
                lock.unlink(missing_ok=True)
    return 1 if failed else 0
