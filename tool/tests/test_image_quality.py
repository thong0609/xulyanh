import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from approve_tool import ROOT, CheckError, atomic_json, digest
from api_providers import ProviderFatal
from image_quality import ImageQualityObserver, ImageQualityGate, protected_image_urls
from run_grouped_shopaikey import ContinuingPipeline, ShopClient, ShopLedger
from source_subject_guard import SourceSubjectClient


def observation(decision='pass', reason='none'):
    return {'status': 'readable', 'texts': ['Hoa Mai'], 'quality_decision': decision,
            'quality_reason': reason, 'quality_evidence': [] if decision == 'pass' else ['visible overlay']}


class Fetch:
    def __init__(self):
        self.page_calls = 0

    def image(self, url):
        return b'image-bytes'

    def page(self, *args):
        self.page_calls += 1
        raise CheckError('TARGET_IMAGE_CONTEXT_NOT_FOUND')


class QualityTests(unittest.TestCase):
    def fixture(self, folder, value, url_match=True):
        calls = []
        def transport(payload):
            calls.append(payload['text']['format']['name'])
            return {'status': 'completed', 'usage': {'input_tokens': 100, 'output_tokens': 30},
                    'output': [{'type': 'message', 'content': [
                        {'type': 'output_text', 'text': json.dumps(value)}]}]}
        ledger = ShopLedger(folder / 'usage.json', 1, (.24, .9))
        client = ShopClient('fake', ledger, folder / 'cache', provider='shopaikey',
                            model='gpt-6-luna', transport=transport)
        client = SourceSubjectClient(ImageQualityObserver(client))
        class Pipeline(ImageQualityGate, ContinuingPipeline):
            output_dir = folder
        fetch = Fetch()
        engine = Pipeline(client, fetch, {}, require_ocr_response=True, one_yes_per_image=False)
        row = {'entity_id': 'e', 'entity_name': 'Trường mầm non Hoa Mai', 'approve': '',
               'image_url': 'https://example.org/truong-mam-non-hoa-mai.jpg' if url_match else 'https://example.org/photo.jpg',
               'page_url': 'https://example.org/article'}
        return engine, fetch, calls, row

    def test_reject_overrides_url_match_for_entire_group(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d);engine, fetch, calls, row = self.fixture(p, observation('reject', 'large_watermark'))
            result = engine.process_group([(0, row, 'r0'), (1, dict(row), 'r1')])
            self.assertEqual([r['approve'] for r in result], ['no', 'no'])
            self.assertEqual({r['reason'] for r in result}, {'IMAGE_QUALITY_REJECTED'})
            self.assertEqual(len(calls), 1)
            self.assertEqual(fetch.page_calls, 0)

    def test_pass_url_match_still_inspects_image(self):
        with tempfile.TemporaryDirectory() as d:
            engine, fetch, calls, row = self.fixture(Path(d), observation())
            result = engine.process_group([(0, row, 'r0')])
            self.assertEqual(result[0]['approve'], 'yes')
            self.assertEqual(result[0]['checks']['image_quality']['quality_decision'], 'pass')
            self.assertEqual(len(calls), 1)

    def test_combined_ocr_not_called_twice(self):
        with tempfile.TemporaryDirectory() as d:
            engine, fetch, calls, row = self.fixture(Path(d), observation(), url_match=False)
            engine.process_group([(0, row, 'r0')])
            self.assertEqual(len(calls), 1)

    def test_review_deferred_once_not_no(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d);engine, fetch, calls, row = self.fixture(p, observation('review', 'map_needs_review'))
            with patch('sys.stdout', new=io.StringIO()), self.assertRaises(ProviderFatal):
                engine.process_group([(0, row, 'r0')])
            self.assertEqual(len(calls), 1)
            self.assertEqual(fetch.page_calls, 0)
            event = json.loads((p / 'deferred_groups.jsonl').read_text())
            self.assertEqual(event['attempts'], 1)
            self.assertTrue(event['error'].startswith('IMAGE_QUALITY_REVIEW'))

    def test_no_reject_without_visible_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            value = observation('reject', 'large_watermark');value['quality_evidence'] = []
            engine, _, calls, row = self.fixture(Path(d), value)
            with patch('sys.stdout', new=io.StringIO()), self.assertRaises(ProviderFatal):
                engine.process_group([(0, row, 'r0')])
            self.assertEqual(len(calls), 1)

    def test_alias_tools_protect_rejects(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'outputs') as d:
            p = Path(d);url = 'https://example.org/shared.jpg'
            (p / 'quality_checks').mkdir()
            atomic_json(p / 'quality_checks/check.json', {'image_url': url, 'quality_decision': 'reject'})
            fields = ['entity_id', 'entity_name', 'image_url', 'page_url', 'approve']
            rows = [dict(zip(fields, ['1', 'Nhà máy nước Gia Bình', url, 'https://example.org', 'yes'])),
                    dict(zip(fields, ['2', 'Nhà máy nước Gia Bình (Bắc Ninh)', url, 'https://example.org', 'no']))]
            source = p / 'selected_rows.csv'
            with source.open('w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=fields);w.writeheader();w.writerows(rows)
            raw = source.read_bytes()
            self.assertEqual(protected_image_urls(source), {url})
            run = subprocess.run([sys.executable, str(ROOT / 'propagate_group_yes.py'),
                                  '--input', str(source), '--apply'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(source.read_bytes(), raw)
            review = p / 'pairs.json'
            atomic_json(review, {'source': str(source), 'source_sha': digest(raw), 'pairs': [{
                'data_row': 2, 'anchor_data_row': 1, 'entity_name': rows[1]['entity_name'],
                'anchor_entity_name': rows[0]['entity_name'], 'reason': 'alias'}]})
            run = subprocess.run([sys.executable, str(ROOT / 'apply_reviewed_group_aliases.py'),
                                  '--review', str(review), '--apply'], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(source.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
