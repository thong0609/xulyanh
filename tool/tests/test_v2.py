"""Regression checks for audited pilot failures; entirely offline."""
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
from matching import profile_name, exact_match, numeric_conflict
from source_page import extract_page
from test_tool import ROW, FakeModel, FakeFetcher


class V2RegressionTests(unittest.TestCase):
    def test_name_parts_and_numeric_conflicts(self):
        for name, text in [('Ga Yên Viên', 'https://a.test/yen-vien'),
                           ('Đường Nguyễn Huệ Quận 1 TP HCM', 'Phố đi bộ Nguyễn Huệ'),
                           ('Phố đi bộ An Thượng Đà Nẵng', 'Chợ đêm An Thượng'),
                           ('Xã nông thôn mới Đồng Tháp, Đan Phượng (Hà Nội)', 'Đồng Tháp')]:
            self.assertTrue(exact_match(profile_name(name), text), name)
        self.assertTrue(numeric_conflict(profile_name('Kênh T2'), 'Kênh T3'))
        self.assertTrue(numeric_conflict(profile_name('Công viên 3 tháng 2'), '3. Du lịch Huế tháng 2'))
        self.assertFalse(numeric_conflict(profile_name('Mầm non 19/5'), 'Mầm non mười chín tháng năm'))
        self.assertFalse(exact_match(profile_name('Khu tập thể cũ Hà Nội'), 'Hà Nội'))
        self.assertFalse(exact_match(profile_name('Nhà kính khu nông nghiệp công nghệ cao TP.HCM'), 'Nhà kính'))

    def test_normalized_evidence_without_inventing_words(self):
        self.assertTrue(app.evidence_present('"Yên Viên"', ['https://a.test/yen-vien']))
        self.assertTrue(app.evidence_present('Chợ đêm An Thượng', ['Chợ đêm An Thượng']))
        self.assertTrue(app.evidence_present('"Phố đi bộ Nguyễn Huệ."', ['Phố đi bộ Nguyễn Huệ.']))
        self.assertFalse(app.evidence_present('Hoa Hồng', ['Hoa Mai']))
        self.assertFalse(app.evidence_present('An', ['Thanh']))

    def test_urls_cards_and_original_image_links(self):
        url = 'https://img.test/cdn-cgi/image/width=700,height=700/https://orig.test/a.jpg'
        html = '<main><div class="card"><h5>Previous</h5></div><div class="card">'
        html += '<a class="card-img-top"><img src="'+url+'"></a><div class="card-body"><h5>Correct</h5>'
        html += 'body '*60 + '</div></div></main>'
        page = extract_page(html, 'https://example.test', url)
        self.assertEqual(page['contexts'][0]['headings'], ['Correct'])
        self.assertNotIn('Previous', page['contexts'][0]['local_text'])
        html = '<main><a href="/original.jpg"><img src="/original-768x543.jpg"></a>'+'text '*60+'</main>'
        self.assertTrue(extract_page(html, 'https://a.test', 'https://a.test/original.jpg')['target_found'])
        html = '<main><img srcset="'+url+' 700w, /large.jpg 1200w">'+'text '*60+'</main>'
        self.assertTrue(extract_page(html, 'https://a.test', url)['target_found'])
        self.assertTrue(extract_page(html, 'https://a.test', 'https://a.test/large.jpg')['target_found'])

    def test_real_cached_pages_from_audit(self):
        path = app.ROOT/'outputs/pilot_v1/audit/audit_inputs.json'
        if not path.exists(): self.skipTest('Local audit cache not distributed')
        rows = json.loads(path.read_text())
        expected = {2: 'Ngôi Nhà Tư Duy', 4: 'Xuân Thới Đông', 14: 'Kim Liên',
                    33: 'Chi hội Một Ngàn', 47: 'nhà kính'}
        for n, phrase in expected.items():
            row = rows[n-1]
            key = app.digest(app.encoded(['pilot-v1', row['page_url'], 'page']))
            data = app.ROOT/'cache/http'/(key+'.bin')
            if not data.exists(): self.skipTest('HTML cache unavailable')
            meta = json.loads(data.with_suffix('.json').read_text())
            page = extract_page(data.read_bytes().decode(meta['charset'], errors='replace'), meta['url'], row['image_url'])
            self.assertTrue(page['target_found'], n)
            sources = [s for c in page['contexts'] for s in c['headings']+[c['alt'],c['local_text']]]
            self.assertTrue(app.evidence_present(phrase, sources), n)
            if n == 33: self.assertEqual(page['contexts'][0]['headings'], ['Chi hội Một Ngàn'])

    def assess(self, result, image=b'image', profile=None):
        # Exercise production validators; stub only model inference.
        client = object.__new__(app.ModelClient)
        client.ask = lambda *args, **kwargs: dict(result)
        page = {'text': 'Kim Liên là khu tập thể cũ tại Hà Nội.', 'incomplete': False,
                'truncated': False, 'target_found': True, 'contexts': [
                    {'headings': ['Khu tập thể Kim Liên'], 'alt': '',
                     'local_text': 'Khu tập thể Kim Liên.', 'local_truncated': False}]}
        return client.assess_page(profile or profile_name('Khu tập thể cũ Hà Nội'), page, image)

    def decision(self, **kwargs):
        return dict({'status': 'match', 'evidence_ids': ['c0_headings_0_0'], 'observed_name': 'Khu tập thể Kim Liên', 'name_relation': 'not_applicable', 'context_index': 0,
                     'explanation': 'test', 'relation': 'instance_of', 'scope_status': 'supported',
                     'supporting_evidence_ids': ['page_0'],
                     'visual_status': 'supports'}, **kwargs)

    def test_supported_member_and_rephrasing(self):
        self.assertEqual(self.assess(self.decision())['status'], 'match')
        self.assertEqual(self.assess(self.decision(relation='same_entity'))['status'], 'match')

    def test_topic_unknown_scope_missing_image_and_absence_stay_blank(self):
        for changes in [{'relation':'same_topic'}, {'scope_status':'unknown'},
                        {'supporting_evidence_ids':[]}, {'visual_status':'contradicts'},
                        {'status':'name_not_found'}, {'status':'other_entity','relation':'different'}]:
            self.assertEqual(self.assess(self.decision(**changes))['status'], 'uncertain', changes)
        self.assertEqual(self.assess(self.decision(), image=None)['status'], 'uncertain')
        with self.assertRaisesRegex(app.CheckError, 'RELATION_EVIDENCE'):
            self.assess(self.decision(supporting_evidence_ids=['invented']))

    def test_generic_greenhouse_does_not_prove_specific_park(self):
        profile = profile_name('Nhà kính khu nông nghiệp công nghệ cao TP.HCM')
        self.assertEqual(profile['scope'], 'group')
        # No source evidence of membership: a semantic model saying same topic cannot approve.
        self.assertEqual(self.assess(self.decision(relation='same_topic', scope_status='unknown'),
                                     profile=profile)['status'], 'uncertain')

    def test_same_50_baseline_and_comparison_export(self):
        with tempfile.TemporaryDirectory(dir=app.ROOT) as tmp:
            root=Path(tmp); (root/'input').mkdir()
            source=root/'input/general_10m_part_02_copy.csv'
            rows=[dict(ROW, entity_id=str(i)) for i in range(60)]
            with source.open('w', newline='') as f:
                w=csv.DictWriter(f, fieldnames=list(ROW)); w.writeheader(); w.writerows(rows)
            _,_,ids,_,_,sha=app.read_csv(source)
            selected=list(range(59,9,-1))  # Explicit ordering unlike random sample.
            baseline=root/'outputs/pilot_v1'; baseline.mkdir(parents=True)
            app.atomic_json(baseline/'manifest.json', {'input_sha256':sha, 'rows':60, 'selected_indices':selected})
            old=[{'row_index':i,'row_id':ids[i],'approve':'','reason':'OLD'} for i in selected]
            (baseline/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in old))
            before={p.name:p.read_bytes() for p in baseline.iterdir()}
            args=['--baseline-dir',str(baseline)]
            with patch.object(app,'ROOT',root), patch('sys.stdout',new_callable=io.StringIO), \
                 patch.dict(app.os.environ,{'OPENAI_API_KEY':'fake-key'}), \
                 patch.object(app,'ModelClient',return_value=FakeModel()), \
                 patch.object(app,'Fetcher',return_value=FakeFetcher()):
                app.main(args)
                app.main(args+['--run'])
                app.main(args+['--run','--resume'])
                with self.assertRaises(app.CheckError): app.main(args+['--output-dir',str(baseline)])
            out=root/'outputs/pilot_v2_2'
            manifest=json.loads((out/'manifest.json').read_text())
            self.assertEqual(manifest['selected_indices'],selected)
            with (out/'pilot_50.csv').open(newline='') as f: sample=list(csv.DictReader(f))
            self.assertEqual([r['entity_id'] for r in sample],[str(i) for i in selected])
            self.assertTrue(all(r['approve']=='no' for r in sample))
            with (out/'comparison_v1_v2.csv').open(encoding='utf-8-sig',newline='') as f: compared=list(csv.DictReader(f))
            self.assertEqual(len(compared),50)
            self.assertTrue(all(r['approve_v1']=='' and r['approve_v2']=='no' for r in compared))
            self.assertEqual(before,{p.name:p.read_bytes() for p in baseline.iterdir()})
            self.assertEqual(app.digest(source.read_bytes()),sha)
            with self.assertRaises(app.CheckError): app.baseline_sample(baseline,'wrong',rows,ids,50)


if __name__=='__main__': unittest.main()
