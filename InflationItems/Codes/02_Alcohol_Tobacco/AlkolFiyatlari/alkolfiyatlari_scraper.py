"""Collect eight alcohol categories and save one daily four-column CSV."""
import argparse
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from daily_csv import fetch_html,save
import whisky_pilot,spirits_pilot,beer_wine_pilot,more_spirits_pilot

CATEGORIES=('whisky','raki','votka','bira','sarap','cin','tekila','likor')
def collect(stamp,load_html=fetch_html):
    rows=[]
    for kind in CATEGORIES:
        slug='viski' if kind=='whisky' else kind
        html=load_html(f'https://alkolfiyatlari.co/{slug}-fiyatlari/')
        if kind=='whisky':items,_=whisky_pilot.parse(html,stamp)
        elif kind in ('raki','votka'):items,_=spirits_pilot.parse(html,stamp,kind)
        elif kind in ('bira','sarap'):items,_=beer_wine_pilot.parse(html,stamp,kind)
        else:items,_=more_spirits_pilot.parse(html,stamp,kind)
        rows.extend(dict(category=kind,**r) for r in items)
    return rows
def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parents[3]/'Datas/02_Alcohol_Tobacco/AlkolFiyatlari')
    parser.add_argument('--replace-day',action='store_true')
    args=parser.parse_args(argv);now=datetime.now(ZoneInfo('Europe/Istanbul'))
    rows=collect(now.isoformat())
    print(f'{len(rows)} urun -> {save(rows,"AlkolFiyatlari",now.date().isoformat(),args.output_dir,args.replace_day)}')
    return 0
if __name__=='__main__':raise SystemExit(main())
