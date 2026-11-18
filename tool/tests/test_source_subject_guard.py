import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from approve_tool import CheckError
from matching import profile_name
from source_subject_guard import refine, SourceSubjectClient


def fixture(entity='Trường Mầm non Bé Thông Minh', subject='Trường Mẫu giáo La Dạ'):
    quote='Tiết dạy học tại '+subject
    answer = dict(winner_id='', rejected_ids=[], different_entity_ids=[], location_conflict_ids=[],
        unconfirmed_branch_ids=[], generic_description_ids=['R0'], evidence_ids=['b0'],
        observed_name=subject, name_relation='not_applicable', explanation='test',
        image_subject_name=subject, image_subject_type='school', image_subject_quote=quote,
        image_subject_evidence_ids=['b0'], image_subject_binding='caption',
        image_subject_other_candidate_ids=[], image_subject_type_conflict_ids=[], generic_reason='test')
    data = {'candidates':[{'record_id':'R0','entity':profile_name(entity)}],
            'blocks':[{'id':'b0','field':'local_text','text':quote+'. Bài báo về giáo dục.'}]}
    return answer, data


class GuardTests(unittest.TestCase):
    def test_other_school_caption_overrides_generic_without_new_request(self):
        a,d=fixture();before=copy.deepcopy(a);r=refine(a,d)
        self.assertEqual(r['different_entity_ids'],['R0'])
        self.assertEqual(r['generic_description_ids'],[])
        self.assertEqual(a,before)

    def test_same_school_caption_remains_yes(self):
        a,d=fixture(entity='Trường Mẫu giáo La Dạ');r=refine(a,d)
        self.assertEqual(r['different_entity_ids'],[])

    def test_translation_winner_preserved(self):
        a,d=fixture(entity='Trường Mầm non Hoa Hồng',subject='Rose Preschool')
        a.update(winner_id='R0', name_relation='translation',generic_description_ids=[])
        self.assertEqual(refine(a,d)['winner_id'],'R0')

    def test_generic_without_bound_subject_remains_yes(self):
        a,d=fixture();a.update(image_subject_binding='unbound',image_subject_quote='',image_subject_evidence_ids=[])
        self.assertEqual(refine(a,d)['generic_description_ids'],['R0'])

    def test_navigation_or_unverified_quote_cannot_override(self):
        for change in ('heading','invented_quote','unknown_block'):
            a,d=fixture()
            if change=='heading':d['blocks'][0]['field']='headings'
            if change=='invented_quote':a['image_subject_quote']='Không xuất hiện trong nguồn'
            if change=='unknown_block':a['image_subject_evidence_ids']=['fake']
            self.assertEqual(refine(a,d)['generic_description_ids'],['R0'])

    def test_power_line_is_not_substation_branch(self):
        a,d=fixture(entity='Trạm biến áp 220kV Đồng Hới',subject='Đường dây 220kV Đông Hà – Đồng Hới')
        a.update(image_subject_type='power line',generic_description_ids=[],unconfirmed_branch_ids=['R0'])
        r=refine(a,d)
        self.assertEqual(r['unconfirmed_branch_ids'],[])
        self.assertEqual(r['different_entity_ids'],['R0'])

    def test_model_conflict_requires_verified_quote(self):
        a,d=fixture();a.update(image_subject_other_candidate_ids=['R0'],image_subject_quote='unverified')
        self.assertEqual(refine(a,d)['different_entity_ids'],[])

    def test_unknown_candidate_id_rejected(self):
        a,d=fixture();a['image_subject_other_candidate_ids']=['fake']
        with self.assertRaises(CheckError):refine(a,d)

    def test_one_source_request_and_new_schema_cache_namespace(self):
        a,d=fixture()
        class Inner:
            calls=[]
            def ask(self,*args):self.calls.append(args);return a
            def observe(self,image):return {'status':'no_text','texts':[]}
        inner=Inner();client=SourceSubjectClient(inner)
        r=client.ask('group_source_user_rules_v4','instruction',d,{'properties':{},'required':[]})
        self.assertEqual(len(inner.calls),1)
        self.assertEqual(inner.calls[0][0],'group_source_subject_guard_v2')
        self.assertIn('image_subject_quote',inner.calls[0][3]['required'])
        self.assertEqual(r['different_entity_ids'],['R0'])

    def test_compatible_accommodation_winner_preserved(self):
        a,d=fixture(entity='Resort Mường Thanh Holiday Mộc Châu',subject='villa Mường Thanh Mộc Châu')
        a.update(winner_id='R0',name_relation='alias',generic_description_ids=[],image_subject_type='villa')
        self.assertEqual(refine(a,d)['winner_id'],'R0')


if __name__=='__main__':unittest.main()
