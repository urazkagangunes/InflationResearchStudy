from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent/'InflationItems/Codes/02_Alcohol_Tobacco/AlkolFiyatlariCo'))
from beer_wine_pilot import parse,BEER,SPECIAL,COMPARE,WINE,RED,MONTHLY

def table(headers,rows=()):
    return '<table><tr>'+''.join(f'<th>{h}</th>' for h in headers)+'</tr>'+''.join('<tr>'+''.join(f'<td>{c}</td>' for c in row)+'</tr>' for row in rows)+'</table>'

def beer():
    return '<h1>Bira Fiyatları</h1><time datetime="2026-09-26T12:00:00+03:00"></time>'+table(BEER,[('Örnek','50 cl depozitolu şişe','123 TL'),('Örnek','50 cl depozitosuz şişe','125 TL'),('Mini','23,7 cl kutu','100 TL')])+table(BEER,[('Belirsiz','Kutu','100 TL')])+table(BEER)+table(COMPARE,[('Örnek','50 cl','123 TL','246 TL')])+table(SPECIAL)

def wine():
    return '<h1>Şarap Fiyatları</h1><time datetime="2026-09-26T12:00:00+03:00"></time>'+table(WINE,[('Örnek Kırmızı / Beyaz','Şarap','500 TL')])+table(RED,[('Örnek Kırmızı (75 cl)','500 TL')])+table(COMPARE)+table(MONTHLY,[('Örnek Beyaz','75 cl','649 TL','670 TL')])+table(MONTHLY)

class BeerWineTests(unittest.TestCase):
    def test_fractional_volume_and_deposit_identity(self):
        rows,report=parse(beer(),'2026-10-15T12:00:00+03:00','bira')
        self.assertEqual(len(rows),3)
        self.assertEqual(next(r['volume_ml'] for r in rows if r['product_name'].startswith('Mini')),'237')
        self.assertEqual({r['deposit_status'] for r in rows},{'unspecified','returnable_amount_unknown','non_returnable'})
        self.assertTrue(all(r['deposit_amount']=='' for r in rows))
        self.assertEqual(len(report['review']),1)
        self.assertEqual(len(report['skipped_tables']),1)

    def test_wine_current_column_not_previous_price(self):
        rows,report=parse(wine(),'2026-10-15T12:00:00+03:00','sarap')
        self.assertEqual(len(rows),2)
        row=next(r for r in rows if r['product_name'].startswith('Örnek Beyaz'))
        self.assertEqual(row['price'],'670.00')
        self.assertEqual(row['price_period'],'2026-10')
        self.assertEqual(row['effective_from'],'')
        self.assertEqual(len(report['review']),1)

    def test_conflicts_removed_and_unknown_headers_fail(self):
        html=beer().replace(table(SPECIAL),table(SPECIAL,[('Örnek','50 cl depozitolu şişe','130 TL')]))
        rows,report=parse(html,'2026-10-15T12:00:00+03:00','bira')
        self.assertEqual(len(rows),2)
        self.assertTrue(any(r['reason']=='Celiskili fiyatlar.' for r in report['review']))
        with self.assertRaises(ValueError):
            parse(beer().replace('Litre Fiyatı','Birim Fiyat'),'2026-10-15T12:00:00+03:00','bira')

if __name__=='__main__':unittest.main()
