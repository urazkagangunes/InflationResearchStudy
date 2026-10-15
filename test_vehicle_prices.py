"""Offline publishing checks; no browser or network required."""
import csv
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent / 'InflationItems/Codes/07_Transport/VehiclePrices'))
from transport_common import parse_price, publish
from run_prices import main

class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.row = dict(product_name='Ornek urun', price='1234.56', campaign_price='', model_year='',
                        collected_at='2026-10-15T12:00:00+03:00', price_type='list', price_label='Liste', source_url='https://example.com')

    def tearDown(self):
        self.temp.cleanup()

    def test_repeat_protection_and_archive(self):
        path = publish(self.root, 'Toyota', '2026-10-15', [self.row])
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            publish(self.root, 'Toyota', '2026-10-15', [self.row])
        self.assertEqual(path.read_bytes(), before)
        changed = dict(self.row, price='1300.00')
        publish(self.root, 'Toyota', '2026-10-15', [changed], replace=True)
        self.assertEqual(len(list(path.parent.glob('*.csv'))), 1)
        archives = list((path.parent / 'archive').rglob('*.csv'))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_bytes(), before)
        with path.open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(next(csv.DictReader(stream))['price'], '1300.00')

    def test_invalid_data_does_not_replace_valid_day(self):
        path = publish(self.root, 'Toyota', '2026-10-15', [self.row])
        before = path.read_bytes()
        for rows in ([], [dict(self.row, price='0.00')], [dict(self.row, price='NaN')],
                     [self.row, self.row], [dict(self.row, collected_at='2026-10-14')]):
            with self.assertRaises(ValueError):
                publish(self.root, 'Toyota', '2026-10-15', rows, replace=True)
            self.assertEqual(path.read_bytes(), before)

    def test_concurrent_publish_preserves_lock(self):
        folder = self.root / 'Toyota'
        folder.mkdir()
        lock = folder / '.publish.lock'
        lock.write_text('another process')
        with self.assertRaises(FileExistsError):
            publish(self.root, 'Toyota', '2026-10-15', [self.row])
        self.assertTrue(lock.exists())

    def test_turkish_price(self):
        self.assertEqual(parse_price('1.234,56 TL'), '1234.56')
        self.assertIsNone(parse_price('—'))
        for text in ('0 TL', '1.234,56 - 2.000 TL', 'abc'):
            with self.assertRaises(ValueError):
                parse_price(text)

    def test_runner_non_interactive_does_not_load_browser_sources(self):
        with patch('run_prices.importlib.import_module') as load:
            self.assertEqual(main(['--sources', 'Decathlon', 'Salcano', '--non-interactive', '--data-root', str(self.root)]), 0)
            load.assert_not_called()

    def test_runner_continues_after_source_failure(self):
        import json
        good = SimpleNamespace(collect=lambda **kwargs: ([self.row], None, ['unavailable'], 2))
        from unittest.mock import Mock
        loader = Mock(side_effect=[RuntimeError('source failed'), good])
        with patch('run_prices.importlib', SimpleNamespace(import_module=loader)):
            self.assertEqual(main(['--sources', 'Toyota', 'Lastikcim', '--data-root', str(self.root)]), 1)
        report = json.loads((self.root / 'Lastikcim/lastikcim_2026-10-15.json').read_text(encoding='utf-8'))
        self.assertEqual(report['unavailable'], ['unavailable'])
        self.assertFalse((self.root / 'Lastikcim/.collect.lock').exists())

if __name__ == '__main__':
    unittest.main()
