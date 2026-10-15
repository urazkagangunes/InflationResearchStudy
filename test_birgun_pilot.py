from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent/'InflationItems/Codes/02_Alcohol_Tobacco/AlkolFiyatlariCo'))
from birgun_pilot import parse

def page():
    return '''<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-08-06T10:00:00+03:00","dateModified":"2026-08-06T11:00:00+03:00"}</script>
    <div class="contentdetail"><h2>PHİLİP MORRİS GÜNCEL FİYAT LİSTESİ</h2>
    <p>6 Ağustos 2026 Perşembe gününden itibaren geçerli fiyatlar:</p>
    <ul><li>Örnek Kısa: 120 TL<li>Örnek Blue / White: 125 TL<li>Örnek Roll 50 (Kıyılmış Tütün): 150 TL</ul></div>'''

class NewsTests(unittest.TestCase):
    def test_unclosed_list_tags_and_unstated_quantities(self):
        rows,report=parse(page(),'2026-10-15T12:00:00+03:00')
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]['price'],'120.00')
        self.assertEqual(rows[2]['quantity'],'')
        self.assertEqual(rows[0]['effective_from'],'2026-08-06')
        self.assertEqual(report['ready_for_index'],0)
        self.assertEqual(report['grouped_rows'],1)

    def test_changed_price_or_missing_effective_date_fails(self):
        for html in (page().replace('120 TL','120–130 TL'),page().replace('itibaren geçerli','liste duyurusu')):
            with self.assertRaises(ValueError):
                parse(html,'2026-10-15T12:00:00+03:00')

    def test_future_article_fails(self):
        with self.assertRaises(ValueError):
            parse(page(),'2026-08-05T12:00:00+03:00')

    def test_list_nested_in_unclosed_paragraph_is_read(self):
        html=page().replace('fiyatlar:</p>', 'fiyatlar:').replace('</ul>', '</ul></p>')
        rows,report=parse(html,'2026-10-15T12:00:00+03:00')
        self.assertEqual(len(rows),3)

if __name__=='__main__':
    unittest.main()
