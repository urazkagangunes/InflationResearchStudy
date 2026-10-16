from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent/'InflationItems/Codes/07_Transport/VehiclePrices'))
from decathlon_live import parse_html

def card(code):
    return f'<div class="dpb-holder" data-supermodelid="{code}"><a class="product-title" href="/p/bisiklet/R-p-{code}">Ornek Bisiklet</a><span aria-label="fiyat">1.000 TL</span></div>'

class IdentityTests(unittest.TestCase):
    def test_same_title_with_distinct_product_codes_is_retained(self):
        rows,excluded,next_url=parse_html(card('123')+card('456'),'2026-10-16T11:00:00+03:00')
        self.assertEqual(len(rows),2)
        self.assertEqual(len({r['source_url'] for r in rows}),2)

    def test_duplicate_product_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_html(card('123')+card('123'),'2026-10-16T11:00:00+03:00')

if __name__=='__main__':unittest.main()
