import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import approve_tool as app
from matching import profile_name, exact_match
from source_page import extract_page


class MatchingTests(unittest.TestCase):
    def test_number_names_and_dates(self):
        for name, observed in [
            ('Trường Mầm non 8', 'TRƯỜNG MẦM NON TÁM'),
            ('Trường Mầm non 19/5', 'Trường Mầm Non Mười Chín Tháng Năm'),
            ('Trường Mầm non 19/5', 'https://example.com/mam-non-19-thang-5'),
            ('Trường Mầm non 19/5', 'https://example.com/mam-non-19-5'),
            ('Trường Mầm non Hoa Hồng — Nghĩa Tân', 'Hoa Hồng Kindergarten'),
        ]:
            with self.subTest(name=name, observed=observed):
                self.assertIsNotNone(exact_match(profile_name(name), observed))

    def test_false_numeric_and_substring_matches(self):
        for name, observed in [
            ('Mầm non 8', 'Ngày 8/3, ảnh rộng 800px'),
            ('Mầm non 8', 'https://example.com/2026/8/id-8'),
            ('Mầm non 8', 'Trường mầm non 18'),
            ('Mầm non 19/5', 'Trường mầm non 19/6'),
            ('Mầm non Hoa Hồng', 'Trường Mầm non Hoa Mai'),
            ('Mầm non An', 'thanh'),
        ]:
            with self.subTest(name=name, observed=observed):
                self.assertIsNone(exact_match(profile_name(name), observed))

    def test_alias(self):
        p = profile_name('Mầm non Hoa Hồng', {'aliases': ['Rose Preschool']})
        self.assertIsNotNone(exact_match(p, 'Rose Preschool'))


class SourceTests(unittest.TestCase):
    def test_multi_entity_scope(self):
        html = '''<main><h1>Danh sách trường</h1><h2>Hoa Hồng</h2>
          <figure><img src="/a.jpg"><figcaption>Lớp Hoa Hồng</figcaption></figure>
          <h2>Hoa Mai</h2><figure><img data-src="/b.jpg"><figcaption>Lớp Hoa Mai</figcaption></figure>
          <p>''' + 'Nội dung đầy đủ về các trường. ' * 20 + '''</p></main>
          <aside><img src="/a.jpg">Quảng cáo Hoa Mai</aside>'''
        p = extract_page(html, 'https://example.org/post', 'https://example.org/b.jpg')
        self.assertTrue(p['target_found'])
        self.assertEqual(len(p['contexts']), 1)
        self.assertEqual(p['contexts'][0]['headings'][-1], 'Hoa Mai')
        self.assertNotIn('Hoa Hồng', p['contexts'][0]['local_text'])
        self.assertFalse(p['incomplete'])

    def test_multiple_articles_and_article_header_preserved(self):
        html = '<article><header><h1>Hoa Hồng</h1></header>' + 'nội dung '*40 + '</article>'
        html += '<article><h2>Hoa Mai</h2><img src="/b.jpg">' + 'khác '*50 + '</article>'
        page = extract_page(html, 'https://example.org/', 'https://example.org/b.jpg')
        self.assertIn('Hoa Hồng', page['text'])
        self.assertIn('Hoa Mai', page['text'])
        self.assertTrue(page['target_found'])

    def test_dynamic_and_blocked_pages(self):
        for html in ['<div id="app"></div>', '<h1>Verify you are human</h1>' + 'x'*300]:
            self.assertTrue(extract_page(html, 'https://a.test', 'https://a.test/i')['incomplete'])

    def test_query_identity_preserved(self):
        p = extract_page('<main><img src="/i?id=1">'+'text '*70+'</main>',
                         'https://a.test', 'https://a.test/i?id=2')
        self.assertFalse(p['target_found'])

    def test_srcset_and_truncation(self):
        p = extract_page('<main><img srcset="/small.jpg 200w, /large.jpg 1200w">'+'hello '*100+'</main>',
                         'https://a.test', 'https://a.test/large.jpg', max_chars=200)
        self.assertTrue(p['target_found']); self.assertTrue(p['truncated'])


ROW = {'entity_id': 'id', 'entity_name': 'Trường Mầm non Hoa Hồng — Nghĩa Tân',
       'image_url': 'https://example.org/image.jpg', 'page_url': 'https://example.org/article',
       'approve': '', 'leaf_label': 'Trường mầm non & nhà trẻ', 'mo_ta': 'MÔ TẢ KHÔNG ĐƯỢC GỬI'}


class FakeFetcher:
    image_error = False
    page_error = False
    def image(self, url):
        if self.image_error: raise app.CheckError('IMAGE_NETWORK')
        return b'image'
    def page(self, url, image_url):
        if self.page_error: raise app.CheckError('HTTP_403')
        return {'incomplete': False, 'truncated': False, 'contexts_truncated': False,
                'text': 'Không có tên trường.', 'target_found': False, 'contexts': []}


class FakeModel:
    texts = []
    observation = 'no_text'
    page_status = 'name_not_found'
    compare_status = 'not_match'
    def observe(self, image): return {'status': self.observation, 'texts': self.texts}
    def compare(self, profile, texts, context):
        return {'status': self.compare_status, 'evidence': texts[0], 'explanation': 'fake'}
    def assess_page(self, profile, page): return {'status': self.page_status, 'evidence': ''}


class PipelineTests(unittest.TestCase):
    def process(self, row=None, model=None, fetcher=None):
        return app.Pipeline(model or FakeModel(), fetcher or FakeFetcher()).process(row or ROW, 'key', 0)

    def test_image_yes_shortcircuits(self):
        model = FakeModel(); model.texts = ['TRƯỜNG MẦM NON HOA HỒNG']; model.observation = 'readable'
        model.assess_page = lambda *a: self.fail('Should not fetch page')
        self.assertEqual(self.process(model=model)['reason'], 'IMAGE_NAME_MATCH')

    def test_image_error_but_url_yes(self):
        fetcher = FakeFetcher(); fetcher.image_error = True
        row = dict(ROW, page_url='https://example.org/mam-non-hoa-hong')
        self.assertEqual(self.process(row=row, fetcher=fetcher)['approve'], 'yes')

    def test_no_name_means_no_when_all_checks_completed(self):
        self.assertEqual(self.process()['approve'], 'no')

    def test_incomplete_steps_stay_blank(self):
        fetcher = FakeFetcher(); fetcher.image_error = True
        self.assertEqual(self.process(fetcher=fetcher)['approve'], '')
        fetcher = FakeFetcher(); fetcher.page_error = True
        self.assertEqual(self.process(fetcher=fetcher)['approve'], '')
        model = FakeModel(); model.observation = 'unreadable'
        self.assertEqual(self.process(model=model)['approve'], '')
        model = FakeModel(); model.compare_status = 'uncertain'
        self.assertEqual(self.process(model=model)['approve'], '')

    def test_other_section_is_no(self):
        model = FakeModel(); model.page_status = 'other_entity'
        self.assertEqual(self.process(model=model)['approve'], 'no')

    def test_soft_match_goes_through_model(self):
        model = FakeModel(); model.texts = ['Rose Preschool']; model.observation = 'readable'
        model.compare_status = 'match'
        value = self.process(model=model)
        self.assertEqual(value['approve'], 'yes')
        self.assertEqual(value['checks']['image_match']['method'], 'model_semantic')


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=app.ROOT)
        self.root = Path(self.tmp.name)
        self.ledger = app.Ledger(self.root/'usage.json', .50)
    def tearDown(self): self.tmp.cleanup()
    def response(self, obj):
        return {'status': 'completed', 'usage': {'input_tokens': 100, 'output_tokens': 50},
                'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(obj)}]}]}

    def test_schema_cache_and_accounting(self):
        calls = []
        def transport(payload):
            calls.append(payload)
            self.assertNotIn('entity', json.dumps(payload))
            return self.response({'status': 'no_text', 'texts': []})
        client = app.ModelClient('fake-key', self.ledger, self.root/'cache', transport)
        client.observe(b'fake-image'); client.observe(b'fake-image')
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.ledger.report()['api_attempts'], 1)
        self.assertAlmostEqual(self.ledger.total(), .0003)

    def test_failed_call_reserves_budget_on_resume(self):
        def fail(payload): raise app.CheckError('API_NETWORK_ERROR')
        client = app.ModelClient('fake-key', self.ledger, self.root/'cache', fail)
        with self.assertRaises(app.CheckError): client.observe(b'fake-image')
        self.assertGreater(self.ledger.total(), 0)
        again = app.Ledger(self.root/'usage.json', .50)
        self.assertEqual(again.total(), self.ledger.total())

    def test_budget_prevents_request(self):
        self.ledger.budget = .000001
        client = app.ModelClient('fake-key', self.ledger, self.root/'cache', lambda p: self.fail('Paid call'))
        with self.assertRaises(app.BudgetExceeded): client.observe(b'image')

    def test_invented_evidence_is_rejected(self):
        client = app.ModelClient('fake-key', self.ledger, self.root/'cache',
                lambda p: self.response({'status': 'match', 'evidence_ids': ['invented'], 'observed_name': 'Hoa Hồng', 'name_relation': 'exact', 'explanation': ''}))
        with self.assertRaisesRegex(app.CheckError, 'EVIDENCE'):
            client.compare(profile_name('Hoa Hồng'), ['Hoa Mai'], 'image')

    def test_numeric_identity_cannot_be_overridden_by_model(self):
        client = app.ModelClient('fake-key', self.ledger, self.root/'cache',
                lambda p: self.response({'status': 'match', 'evidence_ids': ['obs_0'], 'observed_name': 'Mầm non 19/6', 'name_relation': 'number_equivalent', 'explanation': ''}))
        value = client.compare(profile_name('Mầm non 19/5'), ['Mầm non 19/6'], 'image')
        self.assertEqual(value['status'], 'uncertain')

    def test_concurrent_budget_reservations(self):
        from concurrent.futures import ThreadPoolExecutor
        def reserve(_):
            try: self.ledger.reserve(.20); return True
            except app.BudgetExceeded: return False
        with ThreadPoolExecutor(max_workers=3) as pool:
            accepted = list(pool.map(reserve, range(3)))
        self.assertEqual(sum(accepted), 2)
        self.assertAlmostEqual(self.ledger.total(), .40)

    def test_page_evidence_requires_actual_image_context(self):
        client = app.ModelClient('fake-key', self.ledger, self.root/'cache', lambda p: self.response({
            'status': 'match', 'evidence_ids': ['c0_alt_0_0'], 'observed_name': 'Hoa Hồng', 'name_relation': 'exact', 'context_index': 0, 'explanation': '',
            'relation': 'same_entity', 'scope_status': 'supported',
            'supporting_evidence_ids': [], 'visual_status': 'not_checked'}))
        page = {'text': 'Hoa Hồng', 'contexts': [], 'incomplete': False, 'truncated': False}
        with self.assertRaisesRegex(app.CheckError, 'PAGE_EVIDENCE'):
            client.assess_page(profile_name('Mầm non Hoa Hồng'), page)

    def test_incomplete_json_is_error(self):
        client = app.ModelClient('fake-key', self.ledger, self.root/'cache', lambda p:self.response({'status':'no_text'}))
        with self.assertRaisesRegex(app.CheckError, 'INVALID_JSON'): client.observe(b'image')


class ExportAndCliTests(unittest.TestCase):
    def test_offline_and_mock_50_rows_resume(self):
        with tempfile.TemporaryDirectory(dir=app.ROOT) as tmp:
            root = Path(tmp); (root/'input').mkdir()
            source = root/'input/general_10m_part_02_copy.csv'
            fields = list(ROW)
            rows = [dict(ROW, entity_id=str(i), entity_name=f'Trường Mầm non Hoa Hồng {i}',
                         approve='yes' if i == 0 else '', leaf_label=f'Nhóm {i%7}') for i in range(65)]
            with source.open('w', newline='', encoding='utf-8-sig') as f:
                w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
            before = source.read_bytes()
            with patch.object(app, 'ROOT', root), patch('sys.stdout', new_callable=io.StringIO), \
                 patch.dict(app.os.environ, {'OPENAI_API_KEY':'fake-test-key'}):
                self.assertEqual(app.main([]), 0)
                preview = json.loads((root/'outputs/pilot_v2_2/sample_preview.json').read_text())
                self.assertEqual(len(preview['samples']), 50)
                self.assertFalse((root/'outputs/pilot_v2_2/reviewed.csv').exists())
                # Real pipeline + real CSV/checkpoint/export; all network and model calls fake.
                with patch.object(app, 'ModelClient', return_value=FakeModel()), \
                     patch.object(app, 'Fetcher', return_value=FakeFetcher()):
                    self.assertEqual(app.main(['--run']), 0)
                    self.assertEqual(app.main(['--run', '--resume']), 0)
                    with self.assertRaises(app.CheckError): app.main(['--run'])
                out = root/'outputs/pilot_v2_2/reviewed.csv'
                with out.open(encoding='utf-8-sig', newline='') as f: actual=list(csv.DictReader(f))
                self.assertEqual(len(actual), len(rows))
                selected = set(preview['manifest']['selected_indices'])
                for i, (original, new) in enumerate(zip(rows, actual)):
                    self.assertEqual({k:v for k,v in original.items() if k!='approve'},
                                     {k:v for k,v in new.items() if k!='approve'})
                    self.assertEqual(new['approve'], 'no' if i in selected else original['approve'])
                lines = (root/'outputs/pilot_v2_2/results.jsonl').read_text().splitlines()
                self.assertEqual(len(lines), 50)
                self.assertEqual(before, source.read_bytes())
                # Changed snapshot must not reuse old decisions.
                source.write_bytes(before+b'\n')
                with self.assertRaisesRegex(app.CheckError,'Snapshot'):
                    app.main(['--run', '--resume'])

    def test_restrict_paths(self):
        with self.assertRaises(app.CheckError): app.within(app.ROOT.parent/'general_10m_part_02.csv',app.ROOT/'input')
        with self.assertRaises(app.CheckError): app.within(app.ROOT/'input/x.csv',app.ROOT/'outputs')


if __name__ == '__main__': unittest.main()
