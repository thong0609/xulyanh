"""Fast2 name and page coverage tests. No model, API or network required."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'kaggle'))
from qwen_policy import ConservativeQwenPolicy, verified_identity
from matching import profile_name
from approve_tool import CheckError


def decision(status='name_not_found', **kw):
    v=dict(status=status,evidence_ids=[],observed_name='',name_relation='not_applicable',
           relation='unknown',scope_status='unknown',supporting_evidence_ids=[],visual_status='not_checked')
    v.update(kw); return v


class PolicyTests(unittest.TestCase):
    def identity(self, entity, text, relation, override=None):
        return verified_identity(profile_name(entity,override),
            {'observed_name':text,'name_relation':relation},[{'text':text}])

    def test_reject_unrelated_translation_and_number_claims(self):
        for entity,text,relation in [
            ('Hồ chứa nước Long Sơn','VTV TIMES','translation'),
            ('Nhà máy xử lý nước thải Hồ Bảy Mẫu','Safety First','translation'),
            ('Kênh T2 Bắc Hưng Hải','127','number_equivalent'),
            ('Đê tả sông Lục Nam','100','number_equivalent'),
            ('Bia tưởng niệm liệt sĩ Đồi 82','1937-1945','number_equivalent'),
            ('Mầm non 19/5','Mầm non 19/6','number_equivalent'),
            ('Ga Hoa Hồng','Ga Hoa Long','ocr_variant')]:
            with self.subTest(entity=entity): self.assertFalse(self.identity(entity,text,relation))

    def test_valid_names_numbers_configured_translation_and_minor_ocr(self):
        for entity,text,relation in [
            ('Tòa nhà Crescent Plaza','Crescent Plaza','exact'),
            ('Mầm non 19/5','Mầm non mười chín tháng năm','number_equivalent'),
            ('Khu đô thị Lakeview City','Lakeview Cily','ocr_variant')]:
            self.assertTrue(self.identity(entity,text,relation),text)
        self.assertTrue(self.identity('Mầm non Hoa Hồng','Rose Preschool','translation',
                                     {'aliases':['Rose Preschool']}))
        self.assertFalse(self.identity('Mầm non Hoa Hồng','Rose Preschool','translation'))

    def client(self, answer=None):
        c=ConservativeQwenPolicy.__new__(ConservativeQwenPolicy)
        c.calls_seen=[]
        def ask(task,instruction,data,schema,image=None):
            c.calls_seen.append(data)
            return answer(data) if callable(answer) else dict(answer or decision())
        c.ask=ask
        return c

    def page(self,text='Other content. '*1200):
        return {'text':text,'contexts':[], 'incomplete':False,'truncated':False,
                'contexts_truncated':False,'target_found':False}

    def test_long_source_scanned_in_bounded_chunks_before_absence(self):
        c=self.client();page=self.page()
        result=c.assess_page(profile_name('Ga Hải Phòng'),page)
        self.assertEqual(result['status'],'name_not_found')
        self.assertGreater(len(c.calls_seen),1)
        self.assertTrue(result['chunk_audit']['all_blocks_checked'])
        self.assertTrue(all(sum(len(b['text'])+80 for b in d['blocks'])<=c.page_chunk_chars
                            for d in c.calls_seen))

    def test_name_in_last_chunk_prevents_false_absence(self):
        c=self.client();page=self.page('Other content. '*1000+'Ga Hải Phòng')
        self.assertEqual(c.assess_page(profile_name('Ga Hải Phòng'),page)['status'],'uncertain')

    def test_budget_limit_or_incomplete_source_never_absence(self):
        c=self.client();c.max_page_calls=1
        self.assertEqual(c.assess_page(profile_name('Ga Hải Phòng'),self.page())['status'],'uncertain')
        for field in ('truncated','incomplete','contexts_truncated'):
            c=self.client();page=self.page('Short text');page[field]=True
            self.assertEqual(c.assess_page(profile_name('Ga Hải Phòng'),page)['status'],'uncertain')

    def test_context_budget_error_splits_without_losing_source_blocks(self):
        def answer(data):
            if len(data['blocks'])>1: raise CheckError('LOCAL_CONTEXT_TOO_LONG')
            return decision()
        c=self.client(answer)
        result=c.assess_page(profile_name('Ga Hải Phòng'),self.page('other '*300))
        self.assertEqual(result['status'],'name_not_found')
        self.assertEqual(result['chunk_audit']['covered_blocks'],result['chunk_audit']['total_blocks'])
        self.assertTrue(any(x.get('action')=='split_and_retry' for x in result['chunk_audit']['checks']))

    def test_single_block_failure_does_not_become_no(self):
        def answer(data): raise CheckError('LOCAL_CONTEXT_TOO_LONG')
        c=self.client(answer)
        result=c.assess_page(profile_name('Ga Hải Phòng'),self.page('Small text'))
        self.assertEqual(result['status'],'uncertain')
        self.assertFalse(result['chunk_audit']['all_blocks_checked'])

    def test_context_name_match_maps_short_ids_back_to_real_source(self):
        def answer(data):
            return decision('match',evidence_ids=['E0'],observed_name='Ga Hải Phòng',
                            name_relation='exact',relation='same_entity',scope_status='supported')
        c=self.client(answer);page=self.page()
        page['contexts']=[{'headings':['Ga Hải Phòng'],'alt':'','local_text':''}]
        page['target_found']=True
        result=c.assess_page(profile_name('Ga Hải Phòng'),page)
        self.assertEqual(result['status'],'match')
        self.assertEqual(result['evidence_ids'],['c0_headings_0_0'])
        self.assertEqual(len(c.calls_seen),1)

    def test_invented_evidence_and_global_name_cannot_approve_image(self):
        for key in ['E0','fake']:
            c=self.client(decision('match',evidence_ids=[key],observed_name='Ga Hải Phòng',
                name_relation='exact',relation='same_entity',scope_status='supported'))
            result=c.assess_page(profile_name('Ga Hải Phòng'),self.page('Ga Hải Phòng'))
            self.assertEqual(result['status'],'uncertain')

    def test_valid_other_entity_requires_own_typed_caption(self):
        c=self.client(decision('other_entity',evidence_ids=['E0'],observed_name='Ga Yên Viên',
            name_relation='not_applicable',relation='different',scope_status='contradicted'))
        page=self.page('Ga Yên Viên');page['contexts']=[{'headings':['Ga Yên Viên'],'alt':'','local_text':''}]
        self.assertEqual(c.assess_page(profile_name('Ga Hải Phòng'),page)['status'],'other_entity')
        page['contexts']=[{'headings':[],'alt':'','local_text':'Ga Yên Viên'}]
        self.assertEqual(c.assess_page(profile_name('Ga Hải Phòng'),page)['status'],'uncertain')

    def test_unresolved_context_skips_useless_global_scan(self):
        c=self.client(decision('uncertain'))
        page=self.page();page['contexts']=[{'headings':[], 'alt':'Unclear subject','local_text':''}]
        result=c.assess_page(profile_name('Ga Hải Phòng'),page)
        self.assertEqual(result['status'],'uncertain')
        self.assertEqual(len(c.calls_seen),1)
        self.assertFalse(result['chunk_audit']['all_blocks_checked'])

    def test_group_scope_cannot_be_inferred_from_city_alone(self):
        c=self.client(decision('match',evidence_ids=['E0'],observed_name='Kim Liên',
            name_relation='not_applicable',relation='part_of',scope_status='supported',
            supporting_evidence_ids=['E0'],visual_status='supports'))
        page=self.page('Kim Liên ở Hà Nội.');page['contexts']=[
            {'headings':['Kim Liên ở Hà Nội'],'alt':'','local_text':''}]
        result=c.assess_page(profile_name('Khu tập thể cũ Hà Nội'),page,b'image')
        self.assertEqual(result['status'],'uncertain')
        self.assertEqual(result['chunk_audit']['checks'][0]['validation_reason'],'GROUP_QUALIFIERS_UNPROVEN')

    def test_replay_fast1_semantic_approvals_are_all_rejected(self):
        path=Path(__file__).resolve().parents[1]/'outputs/pilot_gpu_v2_2_fast1/results.jsonl'
        if not path.exists(): self.skipTest('Pilot artifacts not distributed')
        count=0
        for row in map(json.loads,path.read_text().splitlines()):
            hit=row.get('checks',{}).get('image_match',{})
            if row['reason']=='IMAGE_NAME_MATCH' and hit.get('method')=='model_semantic':
                count+=1
                self.assertFalse(verified_identity(row['profile'],hit,hit['evidence_blocks']),row['entity_name'])
        self.assertEqual(count,12)


if __name__=='__main__':unittest.main()
