from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent / 'InflationItems/Codes/02_Alcohol_Tobacco/AlkolFiyatlariCo'))
from whisky_pilot import parse

def page(price='1.234,50 TL', heading='Viski (70 cl)'):
    return f'''<h1>Viski Fiyatları</h1><time datetime="2026-10-15T00:00:00+03:00"></time>
    <p>Liste son olarak 13 Ekim 2026 tarihinde kontrol edildi.</p>
    <table><tr><th>{heading}</th><th>Güncel Fiyat</th></tr>
    <tr><td>Örnek Ürün</td><td>{price}</td></tr></table>
    <table><tr><th>Marka</th><th>35 cl</th><th>50 cl</th><th>70 cl</th><th>100 cl</th><th>150/175 cl</th></tr></table>
    <table><tr><th>Ürün (70 cl)</th><th>Güncel Fiyat</th></tr></table>'''

class ParserTests(unittest.TestCase):
    def test_size_price_and_dates_remain_distinct(self):
        rows,report=parse(page(),'2026-10-15T12:00:00+03:00')
        self.assertEqual(rows[0]['price'],'1234.50')
        self.assertEqual(rows[0]['volume_ml'],'700')
        self.assertEqual(rows[0]['source_last_checked_at'],'2026-10-13')
        self.assertEqual(rows[0]['effective_from'],'')
        self.assertEqual(report['accepted'],1)

    def test_ambiguous_size_and_missing_price_fail(self):
        for html in (page(heading='Viski (70/100 cl)'),page(price='—'),page(price='0 TL'),page(price='1.000–2.000 TL')):
            with self.assertRaises(ValueError):
                parse(html,'2026-10-15T12:00:00+03:00')

    def test_future_and_duplicate_records_fail(self):
        duplicate=page().replace('</table>','<tr><td>Örnek Ürün</td><td>1.500 TL</td></tr></table>')
        for html in (duplicate,page().replace('2026-10-15T','2026-10-16T')):
            with self.assertRaises(ValueError):
                parse(html,'2026-10-15T12:00:00+03:00')

    def test_repeated_prices_collapse_and_ambiguous_volume_excluded(self):
        html=page().replace('<th>150/175 cl</th></tr>', '<th>150/175 cl</th></tr><tr><td>Örnek Ürün</td><td>600 TL</td><td>—</td><td>1.234,50 TL</td><td>—</td><td>2.500 TL</td></tr>')
        rows,report=parse(html,'2026-10-15T12:00:00+03:00')
        self.assertEqual({r['volume_ml'] for r in rows},{'350','700'})
        self.assertEqual(report['duplicates_collapsed'],1)
        self.assertTrue(any('Belirsiz hacim' in r['reason'] for r in report['rejected']))

    def test_conflicting_prices_exclude_all_versions_of_identity(self):
        html=page().replace('<th>150/175 cl</th></tr>', '<th>150/175 cl</th></tr><tr><td>Örnek Ürün</td><td>600 TL</td><td>—</td><td>1.300 TL</td><td>—</td><td>—</td></tr>')
        rows,report=parse(html,'2026-10-15T12:00:00+03:00')
        self.assertEqual([r['volume_ml'] for r in rows],['350'])
        self.assertTrue(any('celiskili' in r['reason'] for r in report['rejected']))

if __name__=='__main__':
    unittest.main()
