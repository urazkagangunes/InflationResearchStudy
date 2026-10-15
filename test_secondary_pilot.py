from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent/'InflationItems/Codes/02_Alcohol_Tobacco/AlkolFiyatlariCo'))
from secondary_audit import wow_audit,enucuz_audit

class SecondaryTests(unittest.TestCase):
    def test_only_first_post_and_explicit_conflict_are_audited(self):
        html='''<article class="message--post"><time datetime="2026-02-09T18:00:00+03:00"></time><div class="bbWrapper">
        <table><tr><th>Marka / Ürün</th><th>Güncel Fiyat (TL)</th></tr><tr><td>Örnek</td><td>100 TL</td></tr></table>
        <table><tr><th>Marka</th><th>Fiyat (TL)</th></tr><tr><td>Camel Slender</td><td>100 TL</td></tr></table>
        <ul><li>CAMEL Slender / Deep Blue: 107 TL</li></ul></div></article>
        <article class="message--post"><div class="bbWrapper"><li>CAMEL Slender / Deep Blue: 999 TL</li></div></article>'''
        report=wow_audit(html)
        self.assertEqual(report['bullet_rows'],1)
        self.assertEqual(report['tested_internal_conflicts'][0]['main_price'],'107.00')
        self.assertEqual(report['ready_for_index'],0)

    def test_duplicate_beer_tables_not_double_counted(self):
        table='<table><tr><th>Sıra</th><th>Bira Markası</th><th>Ambalaj Türü</th><th>Fiyat (TL)</th></tr><tr><td>1</td><td>Örnek</td><td>50 cl Kutu</td><td>100 TL</td></tr></table>'
        html='<meta property="article:modified_time" content="2026-01-31T23:57:24+03:00"><article><h1>Bira Fiyatları 2024-2025</h1><p>Güncellendi: 8 Ekim 2026</p>'+table+table+'</article>'
        report=enucuz_audit(html)
        self.assertEqual(report['unique_rows'],1)
        self.assertEqual(report['duplicates_collapsed'],1)
        self.assertEqual(report['visible_updated'],'8 Ekim 2026')
        typography=html.replace('Örnek',"Beck's",1).replace('Örnek','Beck’s',1)
        self.assertEqual(enucuz_audit(typography)['unique_rows'],1)
        with self.assertRaises(ValueError):
            enucuz_audit(html.replace('100 TL</td></tr></table></article>','110 TL</td></tr></table></article>'))

if __name__=='__main__':unittest.main()
