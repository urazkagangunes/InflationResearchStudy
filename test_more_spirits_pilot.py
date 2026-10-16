from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent/'InflationItems/Codes/02_Alcohol_Tobacco/AlkolFiyatlariCo'))
from more_spirits_pilot import parse,CONFIG

def page(kind,records):
    html=f'<h1>{CONFIG[kind]["title"]}</h1><time datetime="2026-10-13T10:00:00+03:00"></time>'
    for headers,(mode,count) in CONFIG[kind]['tables'].items():
        for i in range(count):
            html+='<table><tr>'+''.join(f'<th>{h}</th>' for h in headers)+'</tr>'
            for row in records.get(headers,[]) if i==0 else []:
                html+='<tr>'+''.join(f'<td>{cell}</td>' for cell in row)+'</tr>'
            html+='</table>'
    return html

class MoreSpiritsTests(unittest.TestCase):
    def test_foreign_and_bar_prices_excluded(self):
        html=page('cin',{('Cin (70 cl)','Güncel Fiyat'):[('Örnek Cin','1.200 TL')],
                         ('Mekân Tipi','Cin & Tonik Fiyatı'):[('Bar','500 TL')],
                         ('Şehir','Ortalama Cin & Tonik Fiyatı'):[('Roma','10 €')]})
        rows,report=parse(html,'2026-10-15T12:00:00+03:00','cin')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['volume_ml'],'700')
        self.assertEqual(len(report['skipped_tables']),2)

    def test_liqueur_alias_conflict_and_current_price(self):
        html=page('likor',{
            ('Likör','Hacim','Önceki Fiyat','Ekim 2026 Fiyatı'):[('Nazen Likör Nane','35 cl','750 TL','775 TL'),('A / B','70 cl','100 TL','150 TL')],
            ('Nazen Likör (35 cl)','Önceki Fiyat','Ekim 2026 Fiyatı'):[('Nazen Nane Likörü','299 TL','310 TL')],
            ('Hare Likör','Hacim','Önceki Fiyat','Ekim 2026 Fiyatı'):[('Hare Örnek','50 cl','459 TL','475 TL')]})
        rows,report=parse(html,'2026-10-15T12:00:00+03:00','likor')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['price'],'475.00')
        self.assertEqual(rows[0]['price_period'],'2026-10')
        self.assertEqual(len(report['review']),2)
        self.assertTrue(any(r.get('prices')==['310.00','775.00'] for r in report['review']))

    def test_changed_monthly_header_fails(self):
        with self.assertRaises(ValueError):
            parse(page('likor',{}).replace('Ekim 2026 Fiyatı','Kasım 2026 Fiyatı'),'2026-10-15T12:00:00+03:00','likor')

if __name__=='__main__':unittest.main()
