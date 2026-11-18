import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from review_server import ReviewStore


class BatchSaveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'rows.csv'
        self.path.write_text('entity_name,image_url,approve\na,https://example.com/a,\nb,https://example.com/b,no\nc,https://example.com/c,\n')
        self.store = ReviewStore(self.path)

    def values(self):
        with self.path.open() as f:
            return [r['approve'] for r in csv.DictReader(f)]

    def test_batch_writes_once_and_deduplicates(self):
        import os
        with patch('review_server.os.replace', wraps=os.replace) as replace:
            self.assertEqual(self.store.save_many([0, 1, 0], 'yes'), 2)
            self.assertEqual(replace.call_count, 1)
        self.assertEqual(self.values(), ['yes', 'yes', ''])
        self.assertEqual(self.store.save_many([0, 1], 'yes'), 0)
        self.assertEqual(self.store.save(2, 'no'), 1)
        self.store.save_many([0, 1], '')
        self.assertEqual(self.values(), ['', '', 'no'])

    def test_invalid_batch_changes_nothing(self):
        for indices in ([], None, [0, 99], [0, True], [0, '1']):
            with self.assertRaises(ValueError):
                self.store.save_many(indices, 'yes')
        self.assertEqual(self.values(), ['', 'no', ''])
        self.assertEqual([r['approve'] for r in self.store.rows], ['', 'no', ''])

    def test_failed_write_rolls_back_all_rows(self):
        before = self.path.read_bytes()
        with patch('review_server.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.store.save_many([0, 1], 'yes')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual([r['approve'] for r in self.store.rows], ['', 'no', ''])
        self.assertFalse(list(self.path.parent.glob('.csv-review-*')))

    def test_page_approves_selected_rejects_rest_in_one_write(self):
        import os
        with patch('review_server.os.replace', wraps=os.replace) as replace:
            self.assertEqual(self.store.save_page([0, 2], [2]), 2)
            self.assertEqual(replace.call_count, 1)
        self.assertEqual(self.values(), ['no', 'no', 'yes'])
        self.store.save_page([0, 2], [])
        self.assertEqual(self.values(), ['no', 'no', 'no'])
        self.store.save_page([0, 2], [0, 2])
        self.assertEqual(self.values(), ['yes', 'no', 'yes'])

    def test_invalid_page_never_changes_rows(self):
        before = self.path.read_bytes()
        for indices, selected in (([], []), ([0], [1]), ([0, 99], [0]),
                                  ([0, 0], [0]), ([True], []), ([0], None)):
            with self.assertRaises(ValueError):
                self.store.save_page(indices, selected)
        self.assertEqual(self.path.read_bytes(), before)

    def test_page_failure_rolls_back_both_decisions(self):
        before = self.path.read_bytes()
        with patch('review_server.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.store.save_page([0, 2], [2])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual([r['approve'] for r in self.store.rows], ['', 'no', ''])

    def test_external_changes_are_preserved(self):
        self.path.write_text(self.path.read_text() + 'd,https://example.com/d,\n')
        before = self.path.read_bytes()
        with self.assertRaises(RuntimeError):
            self.store.save_many([0, 1], 'yes')
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
