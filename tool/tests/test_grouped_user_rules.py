import json
from pathlib import Path
import sys,tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from approve_tool import CheckError
from api_economy import StopBudget
from api_providers import ProviderFatal
from grouped_user_rules import UserRulesGroupPipeline
from test_grouped_pipeline import Model,Fetch,row,items
from batch_api import BatchStore,BatchModelClient,NeedsBatch
from test_batch_api import FakeAPI


def answer(winner='',rejected=(),different=(),conflict=(),branch=(),generic=(),subject='',evidence=()):
    return {'winner_id':winner,'rejected_ids':list(rejected),'different_entity_ids':list(different),
        'location_conflict_ids':list(conflict),'unconfirmed_branch_ids':list(branch),
        'generic_description_ids':list(generic),'evidence_ids':list(evidence),
        'observed_name':subject,'name_relation':'not_applicable','explanation':'test'}


class UserRulesTests(unittest.TestCase):
    def group(self):return items(row('Mầm non Hoa Hồng'),row('Mầm non Hoa Mai'))
    def run_group(self,decision,fetch=None,group=None):
        m=Model(decision);f=fetch or Fetch('Một nguồn mô tả khác')
        result=UserRulesGroupPipeline(m,f,require_ocr_response=True).process_group(group or self.group())
        return result,m,f
    def labels(self,rs):return [r['approve'] for r in rs]
    def test_missing_image_and_empty_image_context_are_yes(self):
        class Missing(Fetch):
            def page(self,*a):return {'target_found':False,'incomplete':False,'contexts':[]}
        class Empty(Fetch):
            def page(self,*a):return {'target_found':True,'incomplete':False,'contexts':[{'alt':'','headings':[],'local_text':''}]}
        for fetch in (Missing(),Empty()):
            rs,m,_=self.run_group(None,fetch)
            self.assertEqual(self.labels(rs),['yes','yes']);self.assertEqual(m.calls,0)
            self.assertEqual(rs[0]['reason'],'USER_MISSING_IMAGE_CONTEXT_YES')
    def test_other_source_failures_are_no(self):
        class Failed(Fetch):
            def page(self,*a):raise CheckError('HTTP_403')
        class Incomplete(Fetch):
            def page(self,*a):return {'incomplete':True,'contexts':[]}
        for fetch in (Failed(),Incomplete()):
            rs,m,_=self.run_group(None,fetch)
            self.assertEqual(self.labels(rs),['no','no']);self.assertEqual(m.calls,0)
    def test_single_yes_mode_remains_available(self):
        rs=UserRulesGroupPipeline(Model(answer(generic=['R0','R1'])),Fetch(),one_yes_per_image=True).process_group(self.group())
        self.assertEqual(self.labels(rs),['yes','no'])
    def test_multiple_mode_preserves_existing_labels_and_checks_blank_records(self):
        group=items(row('Hoa Hồng',label='yes'),row('Hoa Mai'))
        rs=UserRulesGroupPipeline(Model(answer(generic=['R1'])),Fetch()).process_group(group)
        self.assertEqual(self.labels(rs),['yes','yes'])

    def test_ocr_failure_is_no_without_calling_source(self):
        class Invalid(Model):
            def observe(self,image):raise CheckError('API_INVALID_JSON')
        f=Fetch();rs=UserRulesGroupPipeline(Invalid(),f).process_group(self.group())
        self.assertEqual(self.labels(rs),['no','no']);self.assertEqual(f.pages,0)
    def test_model_winner_bypasses_name_type_and_evidence_guards(self):
        for d in [answer(winner='R1'),answer(winner='R1',subject='Tên model xác định',evidence=['unknown-block'])]:
            rs,m,_=self.run_group(d)
            self.assertEqual(self.labels(rs),['no','yes']);self.assertEqual(m.calls,1)
            self.assertEqual(rs[1]['reason'],'MODEL_SELECTED_YES')
    def test_explicit_rejections_bypass_evidence_and_entity_type_guards(self):
        rs,_,_=self.run_group(answer(rejected=['R0','R1'],subject='Trường THPT Khác'))
        self.assertEqual(self.labels(rs),['no','no'])
        self.assertTrue(all(r['reason']=='MODEL_REJECTED_NO' for r in rs))
    def test_different_subject_no_even_without_rejected_list(self):
        rs,_,_=self.run_group(answer(different=['R0','R1']))
        self.assertEqual(self.labels(rs),['no','no'])
    def test_explicit_location_conflicts_no_despite_common_brand(self):
        group=items(row('Juno Vincom Bắc Giang',url='https://juno.vn/image.jpg'),
                    row('Juno Sư Vạn Hạnh Mall',url='https://juno.vn/image.jpg'))
        rs,m,_=self.run_group(answer(conflict=['R0','R1']),Fetch('Ảnh cửa hàng Juno'),group)
        self.assertEqual(self.labels(rs),['no','no']);self.assertEqual(m.calls,1)
        self.assertTrue(all(r['reason']=='MODEL_LOCATION_CONFLICT_NO' for r in rs))
    def test_unconfirmed_branch_and_generic_description_yes(self):
        for d in (answer(branch=['R0','R1']),answer(generic=['R0','R1'])):
            rs,_,_=self.run_group(d)
            self.assertEqual(self.labels(rs),['yes','yes'])
    def test_explicit_rejection_overrides_positive_fallback(self):
        rs,_,_=self.run_group(answer(rejected=['R0'],generic=['R0','R1']))
        self.assertEqual(self.labels(rs),['no','yes'])
    def test_invalid_candidate_and_conflicting_winner_are_no(self):
        for d in [answer(winner='fake'),answer(winner='R0',rejected=['R0']),answer(generic=['fake'])]:
            rs,_,_=self.run_group(d)
            self.assertEqual(self.labels(rs),['no','no'])
            self.assertTrue(all(r['reason']=='USER_MODEL_CHECK_ERROR_NO' for r in rs))
    def test_unclassified_model_response_is_no_not_blank(self):
        rs,_,_=self.run_group(answer())
        self.assertEqual(self.labels(rs),['no','no'])
        self.assertTrue(all(r['reason']=='USER_MODEL_UNCLASSIFIED_NO' for r in rs))
    def test_malformed_page_url_is_no_without_group_abort(self):
        rs,_,_=self.run_group(None,group=items(row('Hoa Mai',page='http://[')))
        self.assertEqual(self.labels(rs),['no'])
    def test_budget_and_system_failures_propagate_without_labels(self):
        for error in (StopBudget('limit'),ProviderFatal('quota')):
            class Stopped(Model):
                def observe(self,image):raise error
            with self.assertRaises(type(error)):UserRulesGroupPipeline(Stopped(),Fetch()).process_group(self.group())
    def test_distinct_sources_do_not_share_error_label(self):
        class Sources(Fetch):
            def page(self,url,*a):
                if 'blocked' in url:raise CheckError('HTTP_403')
                return {'incomplete':False,'target_found':False,'contexts':[]}
        group=items(row('Hoa Hồng',page='https://blocked.test'),row('Hoa Mai',page='https://empty.test'))
        rs,_,_=self.run_group(None,Sources(),group)
        self.assertEqual(self.labels(rs),['no','yes'])
    def test_batch_suspends_until_ocr_then_uses_v4_schema(self):
        class V4API(FakeAPI):
            def get(self,bid):
                raw=super().get(bid)
                if raw['status']=='completed':
                    tasks={json.loads(line)['custom_id']:json.loads(line)['body']['text']['format']['name']
                           for line in self.files[raw['input_file_id']].splitlines()}
                    values=[json.loads(line) for line in self.files[raw['output_file_id']].splitlines()]
                    for item in values:
                        if tasks[item['custom_id']]=='group_source_user_rules_v4':
                            item['response']['body']['output'][0]['content'][0]['text']=json.dumps(answer(winner='R1'))
                    self.files[raw['output_file_id']]=b'\n'.join(json.dumps(v).encode() for v in values)
                return raw
        with tempfile.TemporaryDirectory() as tmp:
            store=BatchStore(tmp,'gpt-6-luna',1,.0625,.25);f=Fetch();api=V4API();api.pending=True
            pipeline=UserRulesGroupPipeline(BatchModelClient(store),f,require_ocr_response=True)
            with self.assertRaises(NeedsBatch):pipeline.process_group(self.group())
            job=store.prepare();self.assertFalse(store.submit_or_poll(job,api))
            with self.assertRaises(NeedsBatch):pipeline.process_group(self.group())
            self.assertEqual(f.pages,0)
            api.pending=False;store.submit_or_poll(job,api)
            with self.assertRaises(NeedsBatch):pipeline.process_group(self.group())
            store.submit_or_poll(store.prepare(),api)
            rs=pipeline.process_group(self.group());self.assertEqual(self.labels(rs),['no','yes'])
            self.assertEqual(api.creates,2)

if __name__=='__main__':unittest.main()
