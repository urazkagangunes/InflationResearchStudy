"""Collect the prices displayed in BirGun's source article into a daily CSV.

The filename records the collection day, not the article's price-effective date.
Package sizes are never assumed. Rolling tobacco without an Excel code uses 0.
"""
import argparse
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
sys.path.insert(0,str(HERE.parent/'AlkolFiyatlari'))
from daily_csv import fetch_html,save
from birgun_pilot import parse,URL
def collect(stamp,load_html=fetch_html):
    rows,_=parse(load_html(URL),stamp)
    return [dict(category='sigara' if r['product_type']=='cigarette' else 'tutun',**r) for r in rows]
def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=HERE.parents[2]/'Datas/02_Alcohol_Tobacco/BirGun')
    parser.add_argument('--replace-day',action='store_true')
    args=parser.parse_args(argv);now=datetime.now(ZoneInfo('Europe/Istanbul'))
    rows=collect(now.isoformat())
    print(f'{len(rows)} urun -> {save(rows,"BirGun",now.date().isoformat(),args.output_dir,args.replace_day)}')
    return 0
if __name__=='__main__':raise SystemExit(main())
