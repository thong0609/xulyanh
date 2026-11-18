import json
import csv
import io
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import api_economy as eco
from approve_tool import Ledger, CheckError

ROW=dict(entity_id='1',entity_name='Mầm non Hoa Hồng',image_url='https://example.org/a.jpg',
         page_url='https://example.org/article',approve='')

class Fetch:
    def image(self,url):return b'image'
    def page(self,*a):return {'text':'Other school','contexts':[],'incomplete':False,'truncated':False}

class Model:
    def __init__(self):self.compares=0
    def observe(self,image):return {'status':'readable','texts':['Safety first']}
    def compare(self,*a):self.compares+=1;return {'status':'not_match'}
    def assess_page(self,*a,**kw):return {'status':'name_not_found'}

class EconomyTests(unittest.TestCase):
    def test_resume_can_change_workers_but_not_model_input_or_unknown_code(self):
        base={'budget_usd':3,'workers':3,'code_sha256':'same','model':'gpt-6-luna',
              'input_sha256':'snapshot','selected_indices':[2000,2001]}
        self.assertTrue(eco.compatible_resume(base,{**base,'workers':8}))
        self.assertFalse(eco.compatible_resume(base,{**base,'model':'another-model'}))
        self.assertFalse(eco.compatible_resume(base,{**base,'input_sha256':'other'}))
        self.assertFalse(eco.compatible_resume(base,{**base,'code_sha256':'unrecognised'}))
        self.assertFalse(eco.compatible_resume(base,{**base,'budget_usd':2}))

    def test_invalid_http_url_is_record_level_error_and_does_not_become_no(self):
        from http.client import InvalidURL
        with tempfile.TemporaryDirectory() as d:
            fetcher=eco.ResilientFetcher(d)
            with patch('approve_tool.Fetcher.fetch',side_effect=InvalidURL('bad redirect')):
                with self.assertRaisesRegex(CheckError,'FETCH_INVALID_URL'):
                    fetcher.fetch('https://example.org','page')
                r=eco.EconomyPipeline(Model(),fetcher).process(ROW,'id',0)
            self.assertEqual(r['approve'],'')
            self.assertTrue(any(e['error']=='FETCH_INVALID_URL' for e in r['errors']))

    def test_first_is_physical_prefix_not_first_unlabelled_rows(self):
        rows=[dict(ROW,approve=v) for v in ['yes','','','no','']]
        self.assertEqual(eco.selection(rows,3),[1,2])

    def test_baseline_selection_reuses_exact_indices_and_ids(self):
        from approve_tool import read_csv, baseline_sample, digest, encoded
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'in.csv';base=root/'baseline';base.mkdir()
            rows=[dict(ROW,entity_id=str(i)) for i in range(5)]
            with source.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            actual,_,ids,_,_,sha=read_csv(source)
            (base/'manifest.json').write_text(json.dumps({'input_sha256':sha,'rows':5,'selected_indices':[4,1]}))
            results=[dict(row_index=i,row_id=ids[i],approve='yes',reason='TEST') for i in [4,1]]
            (base/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in results))
            selected,_=baseline_sample(base,sha,actual,ids,2)
            self.assertEqual(selected,[4,1])
            with self.assertRaises(CheckError):baseline_sample(base,'different',actual,ids,2)

    def test_url_match_needs_neither_network_nor_api(self):
        class Never:
            def image(self,*a):self.fail('Unexpected fetch')
        r=eco.EconomyPipeline(None,Never()).process(dict(ROW,page_url='https://a.test/mam-non-hoa-hong'),'id',0)
        self.assertEqual(r['approve'],'yes')
        self.assertEqual(r['reason'],'PAGE_URL_NAME_MATCH')

    def test_one_combined_name_call_and_complete_absence(self):
        m=Model();r=eco.EconomyPipeline(m,Fetch()).process(ROW,'id',0)
        self.assertEqual(m.compares,1);self.assertEqual(r['approve'],'no')

    def test_inaccessible_image_cannot_be_absence_no(self):
        class BadFetch(Fetch):
            def image(self,*a):raise CheckError('NETWORK')
        r=eco.EconomyPipeline(Model(),BadFetch()).process(ROW,'id',0)
        self.assertEqual(r['approve'],'')

    def test_budget_stop_propagates_without_a_completed_blank_label(self):
        class Budget(Model):
            def observe(self,*a):raise eco.StopBudget('BUDGET_LIMIT')
        with self.assertRaises(eco.StopBudget):eco.EconomyPipeline(Budget(),Fetch()).process(ROW,'id',0)

    def test_adjacent_sign_lines_avoid_semantic_call(self):
        class Sign(Model):
            def observe(self,*a):return {'status':'readable','texts':['CRESCENT','PLAZA']}
            def compare(self,*a):raise AssertionError('Unneeded paid comparison')
        r=eco.EconomyPipeline(Sign(),Fetch()).process(dict(ROW,entity_name='Tòa nhà Crescent Plaza'),'id',0)
        self.assertEqual(r['approve'],'yes')

    def test_duplicate_images_share_one_paid_request_under_concurrency(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);calls=[]
            def transport(payload):
                calls.append(payload)
                return {'status':'completed','usage':{'input_tokens':100,'output_tokens':50},
                 'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'status':'no_text','texts':[]})}]}]}
            c=eco.EconomyClient('fake',Ledger(root/'usage.json',1),root/'cache',transport)
            with patch.object(eco,'ROOT',root),ThreadPoolExecutor(3) as pool:
                answers=list(pool.map(c.observe,[b'same']*3))
            self.assertEqual(len(calls),1);self.assertEqual(len(answers),3)

    def test_budget_rejected_before_transport(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            c=eco.EconomyClient('fake',Ledger(root/'usage.json',.00001),root/'cache',
                lambda p:self.fail('Paid request should not be sent'))
            with patch.object(eco,'ROOT',root),self.assertRaises(eco.StopBudget):c.observe(b'new')

    def test_runner_checkpoint_budget_resume_and_prefix_export(self):
        with tempfile.TemporaryDirectory(dir=eco.ROOT) as d:
            root=Path(d);(root/'input').mkdir();(root/'outputs/pilot_v2_2').mkdir(parents=True)
            (root/'name_overrides.json').write_text('{}')
            (root/'outputs/pilot_v2_2/summary.json').write_text(json.dumps(
                {'charged_or_reserved_usd':.2,'processed':50}))
            for name in ('api_economy.py','api_providers.py','approve_tool.py','matching.py','source_page.py'):
                shutil.copy2(eco.ROOT/name,root/name)
            source=root/'input/fixture.csv';out=root/'outputs/run'
            rows=[dict(ROW,entity_id=str(i),approve='yes' if i==0 else '') for i in range(4)]
            with source.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            before=source.read_bytes();fail=[True]
            class Pipeline:
                def process(self,row,row_id,index):
                    if index==2 and fail[0]:raise eco.StopBudget('BUDGET_LIMIT')
                    return dict(row_id=row_id,row_index=index,approve='yes',reason='TEST')
            args=['--input',str(source),'--output-dir',str(out),'--first','3',
                  '--workers','1','--budget-usd','10','--run']
            with patch.object(eco,'ROOT',root),patch.object(eco,'EconomyPipeline',return_value=Pipeline()), \
                    patch.dict('os.environ',{'OPENAI_API_KEY':'fake-test-key'}),patch('sys.stdout',new_callable=io.StringIO):
                self.assertEqual(eco.main(args),2)
                summary=json.loads((out/'summary.json').read_text())
                self.assertEqual((summary['completed'],summary['remaining']),(1,1))
                fail[0]=False
                new_args=list(args);new_args[new_args.index('10')]='12'
                new_args[new_args.index('--workers')+1]='8'
                self.assertEqual(eco.main(new_args+['--resume']),0)
            with (out/'first_rows.csv').open(newline='') as f:first=list(csv.DictReader(f))
            with (out/'reviewed.csv').open(newline='') as f:full=list(csv.DictReader(f))
            self.assertEqual(len(first),3);self.assertEqual(len(full),4)
            self.assertEqual(full[3]['approve'],'')
            self.assertEqual(len((out/'results.jsonl').read_text().splitlines()),2)
            self.assertEqual(source.read_bytes(),before)

    def test_real_payload_shorter_and_output_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);c=eco.EconomyClient('fake',Ledger(root/'usage.json',1),root/'cache')
            payload={'max_output_tokens':1800,'input':[{'content':[{'type':'input_text','text':'{ "a": 1 }'}]}]}
            with patch('approve_tool.ModelClient._post',return_value={}) as send:c._post(payload)
            sent=send.call_args.args[0]
            self.assertEqual(sent['max_output_tokens'],900)
            self.assertEqual(sent['input'][0]['content'][0]['text'],'{"a":1}')

if __name__=='__main__':unittest.main()
