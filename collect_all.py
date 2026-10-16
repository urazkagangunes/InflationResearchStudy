"""Collect isolated run outputs and summarize without mixing historical runs."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
ALCOHOL=('whisky','raki','votka','bira','sarap','cin','tekila','likor')

def summarize(run_dir,statuses):
    run_dir=Path(run_dir)
    all_rows=[];sources={};seen=set();fields=['category']
    for source,state in statuses.items():
        item=dict(state)
        if state['status']!='ok':
            sources[source]=item
            continue
        folder=run_dir/source
        csvs=list(folder.glob('*.csv'))
        reports=list(folder.glob('*.json'))
        if source=='secondary_audit':
            if len(reports)!=1 or csvs:raise ValueError('Tek kaynak kontrol raporu bekleniyordu.')
            item['report']=reports[0].relative_to(run_dir).as_posix()
            sources[source]=item
            continue
        if len(csvs)!=1 or len(reports)!=1:raise ValueError('Kaynak basina tek CSV/JSON cifti bekleniyordu.')
        with csvs[0].open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
        report=json.loads(reports[0].read_text(encoding='utf-8'))
        count=report.get('accepted',report.get('observations'))
        if count!=len(rows):raise ValueError('CSV ve rapor satir sayilari uyusmuyor.')
        item.update(rows=len(rows),csv=csvs[0].relative_to(run_dir).as_posix(),report=reports[0].relative_to(run_dir).as_posix())
        if source in ALCOHOL:
            item['included_in_alcohol_observations']=True
            for row in rows:
                key=(source,row['product_name'].casefold())
                if key in seen:raise ValueError('Ayni kategori/urun tekrarlandi.')
                seen.add(key)
                for key in row:
                    if key not in fields:fields.append(key)
                all_rows.append(dict(category=source,**row))
        else:
            item.update(included_in_alcohol_observations=False,ready_for_index=0)
        sources[source]=item
    summary=dict(run_id=run_dir.name,complete=all(s['status']=='ok' for s in statuses.values()),
                 alcohol_observation_rows=len(all_rows),sources=sources,
                 note='Source observations only. No independent current store verification, no group 02 index integration. Cigarette news and secondary audits excluded from combined alcohol CSV.')
    if all_rows:
        combined=run_dir/'combined_alcohol_observations.csv'
        with combined.open('x',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(all_rows)
        summary['combined_csv']=combined.name
    with (run_dir/'run_summary.json').open('x',encoding='utf-8') as stream:
        json.dump(summary,stream,ensure_ascii=False,indent=2)
    return summary

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,default=ROOT/'reports/runs')
    args=parser.parse_args(argv)
    run_dir=args.output_root.resolve()/datetime.now(ZoneInfo('Europe/Istanbul')).strftime('%Y-%m-%d_%H%M%S_%f')
    run_dir.mkdir(parents=True,exist_ok=False)
    statuses={}
    for source in (*ALCOHOL,'birgun','secondary_audit'):
        command=[sys.executable,str(ROOT/'audit_secondary_sources.py')] if source=='secondary_audit' else [sys.executable,str(ROOT/'run_alcohol_pilot.py'),'--source',source]
        command+=['--output-root',str(run_dir/source)]
        print(f'Basliyor: {source}',flush=True)
        try:
            result=subprocess.run(command,timeout=120,check=False)
            statuses[source]=dict(status='ok' if result.returncode==0 else 'failed',exit_code=result.returncode)
        except subprocess.TimeoutExpired:
            statuses[source]=dict(status='failed',reason='120 saniyelik sure asildi.')
    summary=summarize(run_dir,statuses)
    print(f'Tamamlandi: {summary["complete"]}; {summary["alcohol_observation_rows"]} alkol gozlemi -> {run_dir}')
    return 0 if summary['complete'] else 1

if __name__=='__main__':raise SystemExit(main())
