"""Write one four-column daily CSV, with no reports or JSON outputs."""
import csv
import io
import os
from pathlib import Path
import tempfile
from urllib.request import Request,urlopen
from price_csv import convert

def fetch_html(url):
    with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=40) as response:
        if response.geturl().rstrip('/')!=url.rstrip('/') or 'text/html' not in response.headers.get('Content-Type',''):
            raise ValueError('Beklenmeyen kaynak yaniti')
        raw=response.read(5_000_001)
        if len(raw)>5_000_000:raise ValueError('Kaynak sayfasi fazla buyuk')
    return raw.decode('utf-8')

def save(rows,source,day,output_dir,replace=False):
    if not rows:raise ValueError('Bos veri yazilamaz')
    keys=list(dict.fromkeys(k for r in rows for k in r))
    stream=io.StringIO();writer=csv.DictWriter(stream,keys);writer.writeheader();writer.writerows(rows)
    text,converted=convert(stream.getvalue(),source,2)
    if len({r['product_name'] for r in converted})!=len(converted):raise ValueError('Tekrarlanan urun adi')
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    target=output_dir/f'{source.lower()}_{day}.csv'
    if target.exists() and not replace:raise FileExistsError(target)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8-sig',newline='',dir=output_dir,delete=False) as handle:
            tmp=Path(handle.name);handle.write(text)
        if not replace:
            # Exclusive target creation prevents replacing an existing day's observations.
            with target.open('xb') as out:out.write(tmp.read_bytes())
        else:os.replace(tmp,target)
    finally:
        if tmp is not None:tmp.unlink(missing_ok=True)
    return target
