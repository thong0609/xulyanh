"""Regression cases found in the real v2.1 pilot."""
import json
import unittest
from pathlib import Path
from test_tool import app, ROW, FakeModel, FakeFetcher
from matching import profile_name, exact_match
from source_page import extract_page


class V22Tests(unittest.TestCase):
    def test_proper_names_without_generic_type_words(self):
        for entity, observed in [
            ('Tòa nhà Crescent Plaza (Phú Mỹ Hưng, Q7)', 'CRESCENT PLAZA'),
            ('Khu đô thị Lakeview City', 'https://novaland.com.vn/lakeview-city'),
            ('Sân ga Hải Phòng', 'Ga Hải Phòng'),
            ('Sân gôn Montgomerie Links', 'https://booking.com/hotel/vn/montgomerie-links-villas.vi.html'),
            ('Tháp nước Hàng Đậu (Hà Nội)', 'HÀNG ĐẬU'),
            ('Âu tàu Cái Bé (Kiên Giang)', 'https://a.test/cai-lon-cai-be'),
        ]:
            with self.subTest(entity=entity):
                self.assertTrue(exact_match(profile_name(entity),observed))

    def test_generic_words_require_own_entity_type(self):
        profile=profile_name('Công viên Thiếu nhi Đà Nẵng')
        self.assertFalse(exact_match(profile,'https://a.test/quoc-te-thieu-nhi-01.jpg'))
        self.assertFalse(exact_match(profile,'Hoạt động thiếu nhi tại Đà Nẵng'))
        self.assertTrue(exact_match(profile,'Công viên Thiếu nhi'))
        raw={'status':'match','evidence_ids':['obs_0'],'observed_name':'thiếu nhi',
             'name_relation':'translation','explanation':'bad match'}
        client=object.__new__(app.ModelClient);client.ask=lambda *a,**k:dict(raw)
        result=client.compare(profile,['https://a.test/quoc-te-thieu-nhi'],'URL')
        self.assertEqual(result['status'],'uncertain')

    def test_image_before_child_heading_cannot_borrow_entity_from_later_section(self):
        html='<main><h1>Danh sách địa điểm</h1><img src="/cover.jpg">'
        html+='<div class="toc"><a>Chùa Hạnh Phúc Tăng</a></div>'
        html+='<h2>Chùa Khác</h2><p>'+('thông tin '*30)+'</p>'
        html+='<h2>Chùa Hạnh Phúc Tăng</h2><img src="/correct.jpg"><p>Nội dung đúng.</p></main>'
        cover=extract_page(html,'https://a.test','https://a.test/cover.jpg')
        self.assertNotIn('Hạnh Phúc Tăng',cover['contexts'][0]['local_text'])
        self.assertIn('Hạnh Phúc Tăng',cover['text'])
        correct=extract_page(html,'https://a.test','https://a.test/correct.jpg')
        self.assertEqual(correct['contexts'][0]['headings'][-1],'Chùa Hạnh Phúc Tăng')
        self.assertNotIn('Chùa Khác',correct['contexts'][0]['local_text'])

    def test_adjacent_images_do_not_collect_all_following_sections(self):
        html='<main><h1>Bài tổng hợp</h1><img src="/a.jpg"><p>Caption A</p>'
        html+='<h2>Đối tượng B</h2><img src="/b.jpg"><p>'+('Caption B '*40)+'</p></main>'
        page=extract_page(html,'https://a.test','https://a.test/a.jpg')
        self.assertNotIn('Caption B',page['contexts'][0]['local_text'])

    def test_pilot_cover_image_regression(self):
        path=app.ROOT/'outputs/pilot_v1/audit/audit_inputs.json'
        if not path.exists():self.skipTest('Audit cache not distributed')
        row=json.loads(path.read_text())[33]
        key=app.digest(app.encoded(['pilot-v1',row['page_url'],'page']))
        raw=app.ROOT/'cache/http'/(key+'.bin')
        if not raw.exists():self.skipTest('HTML cache unavailable')
        meta=json.loads(raw.with_suffix('.json').read_text())
        page=extract_page(raw.read_bytes().decode(meta['charset'],errors='replace'),meta['url'],row['image_url'])
        self.assertTrue(page['target_found'])
        self.assertNotIn('Hạnh Phúc Tăng',page['contexts'][0]['local_text'])

    def test_old_pilot_ocr_now_approves_named_signs_without_semantic_call(self):
        path=app.ROOT/'outputs/pilot_v2_1/results.jsonl'
        manifest=path.with_name('manifest.json')
        if not path.exists():self.skipTest('Pilot cache not distributed')
        results={r['row_index']:r for r in map(json.loads,path.read_text().splitlines())}
        indices=json.loads(manifest.read_text())['selected_indices']
        for n in [25,31]:
            old=results[indices[n-1]]
            model=FakeModel();model.observe=lambda image:old['checks']['image_observation']
            model.compare=lambda *a:self.fail('A clear sign should not need another model call')
            model.assess_page=lambda *a:self.fail('A clear sign should not need page lookup')
            row=dict(ROW,entity_name=old['entity_name'])
            result=app.Pipeline(model,FakeFetcher()).process(row,'id',0)
            self.assertEqual(result['approve'],'yes',n)
            self.assertEqual(result['reason'],'IMAGE_NAME_MATCH',n)

    def test_ancestor_heading_cannot_be_primary_image_evidence(self):
        client=object.__new__(app.ModelClient)
        def ask(task,instruction,data,schema,image=None):
            # H1 names A but the image is explicitly in the B section.
            ids={b['id'] for b in data['blocks']}
            self.assertNotIn('c0_headings_0_0',ids)
            self.assertIn('c0_headings_1_0',ids)
            return {'status':'match','evidence_ids':['c0_headings_0_0'],
                    'context_index':0,'explanation':'bad','observed_name':'Hoa Hồng',
                    'name_relation':'exact','relation':'same_entity','scope_status':'supported',
                    'supporting_evidence_ids':[],'visual_status':'not_checked'}
        client.ask=ask
        page={'text':'Hoa Hồng và Hoa Mai','contexts':[{'headings':['Hoa Hồng','Hoa Mai'],
                'alt':'Hoa Mai','local_text':'Hoa Mai'}]}
        with self.assertRaises(app.CheckError):
            client.assess_page(profile_name('Hoa Hồng'),page)


if __name__=='__main__':unittest.main()
