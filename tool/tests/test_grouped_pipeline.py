import json
from pathlib import Path
import sys,tempfile,shutil,io,os
from types import SimpleNamespace
from unittest.mock import patch
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from grouped_pipeline import GroupPipeline,image_groups,page_key


def row(name,url='https://img.test/photo.jpg',page='https://source.test/list',label=''):
    return {'entity_id':name,'entity_name':name,'image_url':url,'page_url':page,'approve':label}
def items(*rows):return [(i,r,'id'+str(i)) for i,r in enumerate(rows)]
class Model:
    def __init__(self,answer=None):self.ocr=0;self.calls=0;self.hits=0;self.answer=answer
    def observe(self,image):self.ocr+=1;return {'status':'no_text','texts':[]}
    def ask(self,*a,**kw):self.calls+=1;return dict(self.answer)
class Fetch:
    def __init__(self,subject='Trường mầm non Hoa Mai'):self.subject=subject;self.pages=0
    def image(self,url):return b'image'
    def page(self,*a):
        self.pages+=1
        return {'incomplete':False,'target_found':True,'text':self.subject,'contexts':[
            {'headings':[self.subject],'alt':self.subject,'local_text':self.subject}]}
def decision(winner='',rejected=(),subject='Trường mầm non Hoa Mai'):
    return {'winner_id':winner,'rejected_ids':list(rejected),'evidence_ids':['c0_headings_0_0'],
        'observed_name':subject,'name_relation':'exact','explanation':'test'}

class GroupedTests(unittest.TestCase):
    def test_first_existing_yes_wins_even_if_other_record_already_yes(self):
        m=Model();f=Fetch()
        result=GroupPipeline(m,f).process_group(items(row('Hoa Hồng',label='yes'),row('Hoa Mai',label='yes')))
        self.assertEqual([r['approve'] for r in result],['yes','no'])
        self.assertEqual((m.calls,m.ocr,f.pages),(0,0,0))
    def test_all_existing_no_needs_no_model(self):
        m=Model();r=GroupPipeline(m,Fetch()).process_group(items(row('A',label='no'),row('B',label='no')))
        self.assertEqual([x['approve'] for x in r],['no','no']);self.assertEqual(m.ocr,0)
    def test_juno_brand_fallback_after_address_check(self):
        m=Model()
        r=GroupPipeline(m,Fetch()).process_group(items(
            row('Juno Sư Vạn Hạnh Mall',url='https://juno.vn/images/stores/b3.jpg'),
            row('Juno Vincom Bắc Giang',url='https://juno.vn/images/stores/b3.jpg')))
        self.assertEqual([x['approve'] for x in r],['yes','no']);self.assertEqual(m.ocr,1)
        self.assertEqual(m.calls,0)
        self.assertEqual(r[0]['reason'],'GROUP_BRAND_FALLBACK')
    def test_one_source_call_for_all_candidates_and_tracking_variants(self):
        m=Model(decision(winner='R1'));f=Fetch()
        r=GroupPipeline(m,f).process_group(items(row('Mầm non Hoa Hồng',page='https://source.test/list?utm_source=a'),
            row('Mầm non Hoa Mai',page='https://source.test/list?srsltid=tracking')))
        self.assertEqual([x['approve'] for x in r],['no','yes'])
        self.assertEqual((m.ocr,m.calls,f.pages),(1,1,1))
    def test_reject_one_does_not_reject_others(self):
        m=Model(decision(rejected=['R0'],subject='Trường mầm non Hoa Đào'))
        r=GroupPipeline(m,Fetch('Trường mầm non Hoa Đào')).process_group(items(row('Mầm non Hoa Hồng'),row('Mầm non Hoa Mai')))
        self.assertEqual([x['approve'] for x in r],['no',''])
    def test_proven_other_subject_can_reject_all_candidates(self):
        m=Model(decision(rejected=['R0','R1'],subject='Trường mầm non Hoa Đào'))
        r=GroupPipeline(m,Fetch('Trường mầm non Hoa Đào')).process_group(items(row('Mầm non Hoa Hồng'),row('Mầm non Hoa Mai')))
        self.assertEqual([x['approve'] for x in r],['no','no'])
    def test_invented_subject_or_unknown_id_cannot_win(self):
        for answer in [decision(winner='R1',subject='Hoa Mai'),decision(winner='fake')]:
            m=Model(answer)
            r=GroupPipeline(m,Fetch('Trường mầm non Hoa Đào')).process_group(items(row('Mầm non Hoa Hồng'),row('Mầm non Hoa Mai')))
            self.assertEqual([x['approve'] for x in r],['',''])
    def test_expansion_uses_entire_snapshot_but_empty_urls_stay_independent(self):
        rows=[row('A',url='shared'),row('B',url=''),row('C',url='shared'),row('D',url='')]
        selected,groups=image_groups(rows,[0,1])
        self.assertEqual(selected,[0,1,2]);self.assertEqual(groups,[[0,2],[1]])
        self.assertNotEqual(page_key('https://x.test/?id=1'),page_key('https://x.test/?id=2'))

    def test_runner_exports_expanded_group_and_can_resume_without_repeating_it(self):
        import csv
        import run_grouped_luna as runner
        from approve_tool import ROOT
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);out=root/'outputs/run';source=root/'main.csv'
            rows=[row('First'),row('Unrelated',url='different'),row('Already verified',label='yes')]
            with source.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            before=source.read_bytes()
            for name in ('run_grouped_luna.py','grouped_pipeline.py','grouped_user_rules.py','address_rules.py','api_economy.py','api_providers.py',
                         'approve_tool.py','matching.py','source_page.py','batch_api.py','grouped_batch.py','name_overrides.json'):
                shutil.copy2(ROOT/name,root/name)
            args=SimpleNamespace(input=source,output_dir=out,model='gpt-6-luna',start_row=1,first=1,
                workers=2,budget_usd=1,save_every=1,run=True,resume=False)
            with patch.object(runner,'ROOT',root),patch.dict(os.environ,{'OPENAI_API_KEY':'fake'}),patch('sys.stdout',new_callable=io.StringIO):
                self.assertEqual(runner.run(args,client_factory=lambda *a,**kw:Model(),fetcher_factory=lambda *a:Fetch()),0)
                args.resume=True
                self.assertEqual(runner.run(args,client_factory=lambda *a,**kw:Model(),fetcher_factory=lambda *a:Fetch()),0)
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['selected'],2);self.assertTrue(summary['complete'])
            self.assertEqual(summary['counts'],{'no':1,'yes':1})
            self.assertEqual(len((out/'results.jsonl').read_text().splitlines()),2)
            self.assertEqual(source.read_bytes(),before)

if __name__=='__main__':unittest.main()
