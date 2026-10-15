from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent/'InflationItems/Codes/02_Alcohol_Tobacco/AlkolFiyatlariCo'))
from spirits_pilot import parse

def page():
    return '''<h1>Votka Fiyatları</h1><time datetime="2026-09-26T12:00:00+03:00"></time>
    <table><tr><th>Votka Markası</th><th>35 cl</th><th>50 cl</th><th>70 cl</th><th>100 cl</th></tr>
    <tr><td>Örnek Blue</td><td>600 TL</td><td>—</td><td>1.200 TL</td><td>1.600 TL</td></tr></table>
    <table><tr><th>Premium Votka (70 cl)</th><th>Güncel Fiyat</th></tr><tr><td>Örnek Premium</td><td>3.000 TL</td></tr></table>
    <table><tr><th>Absolut Vodka</th><th>35 cl</th><th>50 cl</th><th>70 cl</th><th>100 cl</th></tr>
    <tr><td>Güncel fiyat</td><td>700 TL</td><td>900 TL</td><td>1.200 TL</td><td>1.600 TL</td></tr></table>'''

class SpiritsTests(unittest.TestCase):
    def test_unknown_series_not_merged_and_missing_not_zero(self):
        rows,report=parse(page(),'2026-10-15T12:00:00+03:00','votka')
        self.assertEqual(len(rows),4)
        self.assertEqual(len(report['review']),4)
        self.assertEqual(len(report['missing']),1)
        self.assertTrue(all(r['source_last_checked_at']=='' and r['effective_from']=='' for r in rows))

    def test_header_change_fails(self):
        with self.assertRaises(ValueError):
            parse(page().replace('35 cl','35/50 cl'),'2026-10-15T12:00:00+03:00','votka')

    def test_conflict_between_tables_is_excluded(self):
        html=page().replace('Örnek Premium','Örnek Blue')
        rows,report=parse(html,'2026-10-15T12:00:00+03:00','votka')
        self.assertFalse(any(r['volume_ml']=='700' for r in rows))
        self.assertTrue(any(r['reason']=='Celiskili fiyatlar.' for r in report['review']))

if __name__=='__main__':unittest.main()
