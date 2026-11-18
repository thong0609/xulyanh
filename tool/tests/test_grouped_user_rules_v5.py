import copy
import csv
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from approve_tool import CheckError
from address_rules import split_address,rank_addresses
from grouped_user_rules import UserRulesGroupPipeline
from source_page import extract_page
from source_subject_guard import refine_v3,SourceSubjectClient
from group_aliases import compatible_alias
from test_grouped_pipeline import Model,Fetch,row,items
from test_grouped_user_rules import answer
from test_source_subject_guard import fixture


class V5Tests(unittest.TestCase):
    def run_group(self,names,decision=None,fetch=None,model=None):
        m=model or Model(decision);f=fetch or Fetch('Một nguồn mô tả khác')
        rs=UserRulesGroupPipeline(m,f,improved_rules=True).process_group(items(*(row(n) for n in names)))
        return rs,m

    def test_absent_image_pending_not_yes(self):
        class Absent(Fetch):
            def page(self,*a):return {'target_found':False,'incomplete':False,'contexts':[]}
        rs,m=self.run_group(['Nghĩa trang Phú Thọ','Nghĩa trang Đức Thọ'],fetch=Absent())
        self.assertEqual([r['approve'] for r in rs],['',''])
        self.assertTrue(all(r['errors'][0]['error']=='TARGET_IMAGE_NOT_CONFIRMED' for r in rs))
        self.assertEqual(m.calls,0)

    def test_verified_image_without_text_yes_even_if_page_short(self):
        class Empty(Fetch):
            def page(self,*a):
                return extract_page('<img src="https://img.test/photo.jpg">','https://source.test/list','https://img.test/photo.jpg')
        rs,m=self.run_group(['Nghĩa trang Phú Thọ'],fetch=Empty())
        self.assertEqual(rs[0]['approve'],'yes')
        self.assertEqual(rs[0]['reason'],'USER_FOUND_IMAGE_EMPTY_CONTEXT_YES')
        self.assertEqual(rs[0]['errors'],[]);self.assertEqual(m.calls,0)

    def test_http_and_ocr_failures_pending(self):
        class Failed(Fetch):
            def page(self,*a):raise CheckError('HTTP_403')
        class BadOCR(Model):
            def observe(self,*a):raise CheckError('API_INVALID_JSON')
        for model,fetch in [(Model(),Failed()),(BadOCR(),Fetch())]:
            rs,_=self.run_group(['Mầm non Hoa Hồng'],model=model,fetch=fetch)
            self.assertEqual(rs[0]['approve'],'');self.assertTrue(rs[0]['errors'])

    def test_city_is_not_branch_even_if_old_parser_puts_it_in_branch(self):
        candidates=[{'record_id':str(i),'address':split_address(n,'ben xe mien tay')} for i,n in enumerate([
            'Bến xe Miền Tây Bình Tân TP HCM','Bến xe Miền Tây TP.HCM','Bến xe Miền Tây, TP Hồ Chí Minh'])]
        contexts=[{'text':'TP.HCM Cà Mau, xe giường nằm','evidence_ids':['ocr']}]
        winner,audit=rank_addresses(candidates,contexts,{'0','1','2'},strict_branch=True)
        self.assertIsNone(winner)
        self.assertTrue(all('branch' not in r['matched'] for r in audit[0]['scores']))

    def test_actual_street_house_still_identifies_branch(self):
        candidates=[{'record_id':str(i),'address':split_address(n,'juno')} for i,n in enumerate([
            'Juno - 319 Ấp Bắc, Tiền Giang','Juno - 102 Nguyễn Trãi, Quận 5, Hồ Chí Minh'])]
        winner,_=rank_addresses(candidates,[{'text':'Juno 102 Nguyễn Trãi, Hồ Chí Minh','evidence_ids':['caption']}],{'0','1'},strict_branch=True)
        self.assertEqual(winner['record_id'],'1')

    def test_equivalent_airport_names_both_yes_without_extra_model_calls(self):
        rs,m=self.run_group(['Sân bay quốc tế Phú Bài','Sân bay quốc tế Phú Bài (Huế)'],answer(winner='R0'))
        self.assertEqual([r['approve'] for r in rs],['yes','yes'])
        self.assertEqual(rs[1]['reason'],'GROUP_EQUIVALENT_ENTITY_YES')
        self.assertEqual(m.calls,1)
        self.assertIn('group_alias',rs[1]['checks'])

    def test_times_city_reviewed_aliases_auto_expand(self):
        rs,_=self.run_group(['Times City — Vinhomes Times City (Hà Nội)',
            'Khu Vinhomes Times City Hai Bà Trưng','Chung cư Vinhomes Times City'],answer(winner='R0'))
        self.assertEqual([r['approve'] for r in rs],['yes','yes','yes'])

    def test_explicit_conflict_not_overridden_by_alias(self):
        rs,_=self.run_group(['Sân bay quốc tế Phú Bài','Sân bay quốc tế Phú Bài (Huế)'],
            answer(winner='R0',conflict=['R1']))
        self.assertEqual([r['approve'] for r in rs],['yes','no'])
        self.assertEqual(rs[1]['reason'],'MODEL_LOCATION_CONFLICT_NO')

    def test_generic_conflict_negative_wins(self):
        rs,_=self.run_group(['Mầm non Hoa Hồng'],answer(generic=['R0'],conflict=['R0']))
        self.assertEqual(rs[0]['approve'],'no');self.assertFalse(rs[0]['errors'])

    def test_existing_manual_no_not_promoted(self):
        group=items(row('Sân bay quốc tế Phú Bài',label='yes'),row('Sân bay quốc tế Phú Bài (Huế)',label='no'))
        rs=UserRulesGroupPipeline(Model(),Fetch(),improved_rules=True).process_group(group)
        self.assertEqual([r['approve'] for r in rs],['yes','no'])

    def test_no_alias_for_different_phase_or_component(self):
        for a,b in [('Vinhomes Times City','Khu đô thị Times City Park Hill Premium'),
            ('Vinhomes Times City','Hồ Times City'),('Cảng Hải Phòng','Cảng Hải Phòng - bến Vật Cách'),
            ('Cảng Cái Mép','Cảng Cái Mép - Thị Vải'),('Ga Hải Phòng','Sân ga Hải Phòng'),
            ('Phố đi bộ Phạm Ngũ Lão - Võ Thị Sáu (Huế)','Phố đi bộ Phạm Ngũ Lão (Huế)'),
            ('Trường mầm non Sao Sáng 3','Trường mầm non Sao Sáng 5')]:
            self.assertIsNone(compatible_alias(a,b),(a,b))

    def test_ocr_sent_to_source_without_a_second_model_call(self):
        class Capture(Model):
            data=None;task=None
            def ask(self,task,instruction,data,*a):
                self.task=task;self.data=data;return super().ask(task,instruction,data,*a)
        m=Capture(answer(generic=['R0']))
        self.run_group(['Mầm non Hoa Hồng'],model=m)
        self.assertEqual(m.task,'group_source_user_rules_v5')
        self.assertEqual(m.data['image_observation'],{'status':'no_text','texts':[]})
        self.assertEqual(m.calls,1)

    def test_recaptcha_comment_footer_does_not_block_article(self):
        page=extract_page('<article>'+('Nội dung bài báo. '*80)+'<img src="https://img.test/a.jpg">'
            '<p>This site is protected by reCAPTCHA and the Google Privacy Policy.</p></article>',
            'https://source.test','https://img.test/a.jpg')
        self.assertFalse(page['incomplete']);self.assertTrue(page['target_found'])


class V3GuardTests(unittest.TestCase):
    def test_line_does_not_identify_station(self):
        a,d=fixture('Nhà ga đường sắt đô thị Cát Linh','Đường sắt Cát Linh - Hà Đông')
        a.update(image_subject_type='railway line',generic_description_ids=[],unconfirmed_branch_ids=['R0'])
        r=refine_v3(a,d)
        self.assertEqual(r['different_entity_ids'],['R0']);self.assertEqual(r['unconfirmed_branch_ids'],[])

    def test_airport_does_not_identify_services_company(self):
        a,d=fixture('Công ty Cổ phần Dịch vụ Sân bay Quốc tế Cam Ranh','Sân bay quốc tế Cam Ranh')
        a.update(image_subject_type='airport',winner_id='R0',generic_description_ids=[])
        r=refine_v3(a,d)
        self.assertEqual(r['winner_id'],'');self.assertEqual(r['different_entity_ids'],['R0'])

    def test_terminal_of_same_airport_compatible(self):
        a,d=fixture('Sân bay Cam Ranh','Nhà ga quốc tế Cam Ranh')
        a.update(image_subject_type='terminal',different_entity_ids=['R0'],generic_description_ids=[])
        r=refine_v3(a,d)
        self.assertEqual(r['different_entity_ids'],[]);self.assertEqual(r['generic_description_ids'],['R0'])

    def test_location_conflict_survives_component_compatibility(self):
        a,d=fixture('Sân bay Cam Ranh','Nhà ga quốc tế Cam Ranh')
        a.update(image_subject_type='terminal',location_conflict_ids=['R0'],generic_description_ids=[])
        self.assertEqual(refine_v3(a,d)['location_conflict_ids'],['R0'])

    def test_unverified_role_claim_cannot_override(self):
        a,d=fixture('Nhà ga đường sắt đô thị Cát Linh','Đường sắt Cát Linh - Hà Đông')
        a.update(image_subject_quote='invented quote',generic_description_ids=['R0'],image_subject_type='railway line')
        self.assertEqual(refine_v3(a,d)['generic_description_ids'],['R0'])

    def test_v5_guard_gets_separate_cache_task(self):
        a,d=fixture('Sân bay Cam Ranh','Nhà ga quốc tế Cam Ranh')
        class Inner:
            calls=[]
            def ask(self,*args):self.calls.append(args);return a
        inner=Inner()
        SourceSubjectClient(inner).ask('group_source_user_rules_v5','instruction',d,{'properties':{},'required':[]})
        self.assertEqual(len(inner.calls),1)
        self.assertEqual(inner.calls[0][0],'group_source_subject_guard_v3')


class V5RunnerTests(unittest.TestCase):
    def scenario(self,failure='missing'):
        import run_grouped_luna_standard as runner
        from approve_tool import ROOT
        from api_providers import ProviderFatal
        class Sources(Fetch):
            def image(self,url):return url.encode()
            def page(self,url,*a):
                if 'missing' in url:return {'incomplete':False,'target_found':False,'contexts':[]}
                return super().page(url,*a)
        class Flaky(Model):
            def observe(self,image):
                if failure!='missing' and image.endswith(b'/a.jpg'):raise ProviderFatal(failure)
                return super().observe(image)
        a,d=fixture('Mầm non Hoa Hồng','Không xác định tên riêng')
        a.update(winner_id='R0',generic_description_ids=[],image_subject_binding='unbound',
            image_subject_quote='',image_subject_evidence_ids=[])
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);source=root/'source.csv';out=root/'outputs/v5'
            rows=[row('Mầm non Hoa Hồng',url='https://img.test/a.jpg',page='https://missing.test'),
                row('Mầm non Hoa Mai',url='https://img.test/b.jpg')]
            with source.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            before=source.read_bytes()
            names=('run_grouped_luna_standard.py','grouped_pipeline.py','grouped_user_rules.py',
                'address_rules.py','api_economy.py','api_providers.py','approve_tool.py','matching.py',
                'source_page.py','source_subject_guard.py','group_aliases.py','propagate_group_yes.py','name_overrides.json')
            for name in names:shutil.copy2(ROOT/name,root/name)
            args=SimpleNamespace(input=source,output_dir=out,model='gpt-6-luna',execution='standard',
                start_row=1,first=2,workers=1,budget_usd=1,run=True,resume=False,
                policy='user-rules-v5',save_every=1,group_yes='multiple')
            with patch.object(runner,'ROOT',root),patch.dict(os.environ,{'OPENAI_API_KEY':'fake'}),patch('sys.stdout',new_callable=io.StringIO):
                code=runner.run(args,client_factory=lambda *x,**kw:Flaky(a),fetcher_factory=lambda *x:Sources())
            self.assertEqual(code,2)
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['completed'],1);self.assertEqual(summary['counts'],{'yes':1})
            journal=[json.loads(line) for line in (out/'results.jsonl').read_text().splitlines()]
            self.assertEqual([r['row_index'] for r in journal],[1])
            deferred=json.loads((out/'deferred_groups.jsonl').read_text().splitlines()[0])
            self.assertEqual(deferred['error'],'TARGET_IMAGE_NOT_CONFIRMED' if failure=='missing' else failure)
            self.assertEqual(source.read_bytes(),before)

    def test_failed_group_is_not_committed_and_later_group_completes(self):self.scenario()

    def test_model_http500_defers_without_stopping_other_groups(self):self.scenario('API_HTTP_500')

    def test_model_network_failure_defers_without_stopping_other_groups(self):self.scenario('API_NETWORK_ERROR')


if __name__=='__main__':unittest.main()
