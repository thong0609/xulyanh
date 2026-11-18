"""Production validators with stubbed inference, never HTTP/API calls."""
import unittest
from test_tool import app, profile_name


class EvidenceIDTests(unittest.TestCase):
    def client(self, result):
        client=object.__new__(app.ModelClient)
        client.ask=lambda *a,**kw:dict(result)
        return client

    def page(self):
        return {'text':'Ga Hải Phòng. Ga Yên Viên.', 'contexts':[
            {'headings':['Ga Hải Phòng'],'alt':'Phòng chờ tại ga Hải Phòng.',
             'local_text':'Ga Hải Phòng là một di sản kiến trúc.'},
            {'headings':['Ga Yên Viên'],'alt':'Ga Yên Viên','local_text':'Khác.'}],
            'incomplete':False,'truncated':False}

    def decision(self, **changes):
        value={'status':'match','evidence_ids':['c0_alt_0_0','c0_local_text_0_0'],
               'context_index':0,'observed_name':'Ga Hải Phòng','name_relation':'exact',
               'explanation':'alt= hoặc nhiều câu có thể viết ở giải thích.',
               'relation':'same_entity','scope_status':'supported','supporting_evidence_ids':[],
               'visual_status':'not_checked'}
        value.update(changes);return value

    def test_multiple_quotes_resolved_from_source_not_model_explanation(self):
        result=self.client(self.decision()).assess_page(profile_name('Ga Hải Phòng'),self.page())
        self.assertEqual(result['status'],'match')
        self.assertEqual(result['evidence'],'Phòng chờ tại ga Hải Phòng.\nGa Hải Phòng là một di sản kiến trúc.')
        self.assertEqual(result['evidence_blocks'][0]['field'],'alt')

    def test_invented_duplicate_wrong_context_and_global_page_ids_rejected(self):
        for ids in [['fake'],['c0_alt_0_0','c0_alt_0_0'],['c1_alt_0_0'],['page_0']]:
            with self.subTest(ids=ids),self.assertRaisesRegex(app.CheckError,'PAGE_EVIDENCE'):
                self.client(self.decision(evidence_ids=ids)).assess_page(profile_name('Ga Hải Phòng'),self.page())

    def test_no_context_cannot_match_even_if_name_in_article(self):
        with self.assertRaises(app.CheckError):
            self.client(self.decision(context_index=-1,evidence_ids=['page_0'])).assess_page(profile_name('Ga Hải Phòng'),self.page())

    def test_url_ids_resolve_without_copying_slug(self):
        raw={'status':'match','evidence_ids':['obs_0'],'observed_name':'Yên Viên',
             'name_relation':'exact','explanation':'Đọc tên trong URL'}
        result=self.client(raw).compare(profile_name('Ga Yên Viên'),['https://a.test/yen-vien'],'URL')
        self.assertEqual(result['status'],'match')
        self.assertEqual(result['evidence'],'https://a.test/yen-vien')

    def test_url_invalid_id_still_rejected(self):
        raw={'status':'match','evidence_ids':['obs_9'],'observed_name':'Yên Viên',
             'name_relation':'exact','explanation':''}
        with self.assertRaises(app.CheckError):
            self.client(raw).compare(profile_name('Ga Yên Viên'),['https://a.test/yen-vien'],'URL')

    def test_unproven_alias_cannot_equate_different_named_facilities(self):
        page=self.page();page['contexts'][0]={'headings':['Nhà máy xử lý nước thải Yên Xá'],
            'alt':'Nhà máy xử lý nước thải Yên Xá','local_text':'Dự án tại Yên Xá, Hà Nội.'}
        for relation in ['exact','alias']:
            raw=self.decision(evidence_ids=['c0_alt_0_0'],observed_name='Yên Xá',name_relation=relation)
            result=self.client(raw).assess_page(profile_name('Nhà máy xử lý nước thải Hồ Bảy Mẫu'),page)
            self.assertEqual(result['status'],'uncertain')
            self.assertEqual(result['validation_reason'],'NAME_IDENTITY_UNSUPPORTED')

    def test_explicit_source_alias_can_match(self):
        page=self.page();page['text']='Ga Hoa Hồng còn gọi là Ga Hoa Đỏ.'
        page['contexts'][0]={'headings':[],'alt':'Ga Hoa Đỏ','local_text':'Ảnh nhà ga.'}
        raw=self.decision(evidence_ids=['c0_alt_0_0'], observed_name='Ga Hoa Đỏ',
                          name_relation='alias',supporting_evidence_ids=['page_0'])
        self.assertEqual(self.client(raw).assess_page(profile_name('Ga Hoa Hồng'),page)['status'],'match')

    def test_page_blocks_do_not_drop_long_tokens(self):
        text='x'*1201+' kết thúc\nDòng sau'
        blocks=app.evidence_blocks(text,'p')
        self.assertEqual(''.join(b['text'] for b in blocks).replace(' ',''),text.replace(' ','').replace('\n',''))
        self.assertTrue(all(len(b['text'])<=600 for b in blocks))


if __name__=='__main__':unittest.main()
