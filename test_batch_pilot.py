import csv
import json
from pathlib import Path
import tempfile
import unittest
from collect_all import summarize

class BatchTests(unittest.TestCase):
    def test_only_current_successful_alcohol_run_is_combined(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for source in ('whisky','birgun'):
                folder=root/source;folder.mkdir()
                with (folder/'data.csv').open('w',encoding='utf-8-sig',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=['product_name','price']);writer.writeheader();writer.writerow(dict(product_name='Ornek',price='100.00'))
                (folder/'data.json').write_text(json.dumps({'accepted':1}),encoding='utf-8')
            (root/'old').mkdir();(root/'old/old.csv').write_text('old data',encoding='utf-8')
            summary=summarize(root,{'whisky':{'status':'ok'},'birgun':{'status':'ok'},'raki':{'status':'failed'}})
            self.assertEqual(summary['alcohol_observation_rows'],1)
            self.assertFalse(summary['complete'])
            self.assertFalse(summary['sources']['birgun']['included_in_alcohol_observations'])
            self.assertTrue((root/'run_summary.json').exists())

    def test_mismatched_csv_and_json_counts_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'whisky';folder.mkdir()
            (folder/'data.csv').write_text('product_name,price\nOrnek,100.00\n',encoding='utf-8')
            (folder/'data.json').write_text('{"accepted":2}',encoding='utf-8')
            with self.assertRaises(ValueError):summarize(Path(temp),{'whisky':{'status':'ok'}})

if __name__=='__main__':unittest.main()
