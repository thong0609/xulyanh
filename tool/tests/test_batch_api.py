import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from approve_tool import ROOT,CheckError,OCR_SCHEMA
from api_economy import StopBudget
from api_providers import ProviderFatal
from batch_api import BatchStore,BatchModelClient,NeedsBatch
from test_grouped_pipeline import row,Fetch,decision


class FakeAPI:
    def __init__(self,*args):self.creates=0;self.files={};self.jobs={};self.pending=False;self.reverse=True
    def upload(self,path):
        key='file'+str(len(self.files));self.files[key]=path.read_bytes();return key
    def create(self,file_id,metadata):
        self.creates+=1;bid='batch'+str(self.creates)
        self.jobs[bid]={'id':bid,'status':'in_progress','metadata':metadata,'input_file_id':file_id}
        return dict(self.jobs[bid])
    def get(self,bid):
        job=self.jobs[bid]
        if self.pending:return dict(job)
        lines=[]
        for raw in self.files[job['input_file_id']].splitlines():
            req=json.loads(raw);task=req['body']['text']['format']['name']
            answer={'status':'no_text','texts':[]} if task=='observe' else decision(winner='R1')
            lines.append({'custom_id':req['custom_id'],'response':{'status_code':200,'body':{
                'status':'completed','usage':{'input_tokens':100,'output_tokens':25},
                'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(answer)}]}]}}})
        if self.reverse:lines.reverse()
        out='out'+bid;self.files[out]=b'\n'.join(json.dumps(x).encode() for x in lines)
        job.update(status='completed',output_file_id=out);return dict(job)
    def content(self,key):return self.files[key]
    def find(self,metadata):return next((dict(j) for j in self.jobs.values() if j['metadata']==metadata),None)


class BatchTests(unittest.TestCase):
    def make(self,root,budget=1):return BatchStore(root,'gpt-6-luna',budget,.0625,.25)
    def test_suspend_then_resume_from_answer_no_standard_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=self.make(tmp);client=BatchModelClient(store);api=FakeAPI()
            with self.assertRaises(NeedsBatch):client.observe(b'fake')
            with self.assertRaises(NeedsBatch):client.observe(b'fake')
            self.assertEqual(store.report()['batch_requests'],1)
            job=store.prepare();self.assertTrue(store.submit_or_poll(job,api))
            self.assertEqual(client.observe(b'fake'),{'status':'no_text','texts':[]})
            with self.assertRaises(RuntimeError):client._post({})
            self.assertEqual(api.creates,1)
            restored=self.make(tmp);self.assertAlmostEqual(restored.report()['charged_or_reserved_usd'],.000013,places=6)
    def test_unordered_results_match_custom_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=self.make(tmp);client=BatchModelClient(store);api=FakeAPI()
            for im in (b'a',b'b'):
                with self.assertRaises(NeedsBatch):client.observe(im)
            job=store.prepare();store.submit_or_poll(job,api)
            self.assertEqual(len(list(Path(tmp).glob('*.answer.json'))),2)
            self.assertEqual(client.observe(b'a')['status'],'no_text')
    def test_budget_before_queue_and_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=self.make(tmp,budget=.000001)
            with self.assertRaises(StopBudget):BatchModelClient(store).observe(b'fake')
            self.assertIsNone(store.prepare())
    def test_pending_resume_and_uncertain_submission_never_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=self.make(tmp);api=FakeAPI();api.pending=True
            with self.assertRaises(NeedsBatch):BatchModelClient(store).observe(b'fake')
            job=store.prepare();self.assertFalse(store.submit_or_poll(job,api))
            store=self.make(tmp);job=store.prepare();self.assertFalse(store.submit_or_poll(job,api))
            job.pop('batch_id');job['status']='submitting';store.save()
            self.assertFalse(store.submit_or_poll(job,api));self.assertEqual(api.creates,1)
            job.pop('batch_id');job['metadata']={'missing':'true'};job['status']='submitting'
            with self.assertRaisesRegex(ProviderFatal,'UNCERTAIN'):store.submit_or_poll(job,api)
            self.assertEqual(api.creates,1)
    def test_unknown_or_duplicate_output_id_stops(self):
        class Bad(FakeAPI):
            def content(self,key):
                line=json.loads(super().content(key));line['custom_id']='unknown';return json.dumps(line).encode()
        with tempfile.TemporaryDirectory() as tmp:
            store=self.make(tmp)
            with self.assertRaises(NeedsBatch):BatchModelClient(store).observe(b'a')
            with self.assertRaisesRegex(ProviderFatal,'CUSTOM_ID'):store.submit_or_poll(store.prepare(),Bad())
    def test_expired_unexecuted_request_blank_error_and_no_charge(self):
        class Expired(FakeAPI):
            def get(self,bid):
                job=self.jobs[bid];req=json.loads(self.files[job['input_file_id']])
                self.files['expired']=json.dumps({'custom_id':req['custom_id'],
                    'error':{'code':'batch_expired'}}).encode()
                return dict(job,status='expired',error_file_id='expired')
        with tempfile.TemporaryDirectory() as tmp:
            store=self.make(tmp);client=BatchModelClient(store)
            with self.assertRaises(NeedsBatch):client.observe(b'a')
            store.submit_or_poll(store.prepare(),Expired())
            self.assertEqual(store.report()['charged_or_reserved_usd'],0)
            with self.assertRaises(CheckError):client.observe(b'a')
    def test_request_limit_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=self.make(tmp);client=BatchModelClient(store);api=FakeAPI()
            for im in (b'a',b'b'):
                with self.assertRaises(NeedsBatch):client.observe(im)
            job=store.prepare(max_requests=1);self.assertEqual(len(job['keys']),1)
            store.submit_or_poll(job,api)
            job2=store.prepare(max_requests=1);self.assertNotEqual(job['job'],job2['job'])
            store.submit_or_poll(job2,api);self.assertIsNone(store.prepare())
    def test_source_cannot_be_queued_until_ocr_answer_is_validated(self):
        from grouped_pipeline import GroupPipeline
        from test_grouped_pipeline import items
        with tempfile.TemporaryDirectory() as tmp:
            store=self.make(tmp);api=FakeAPI();api.pending=True
            client=BatchModelClient(store);fetch=Fetch()
            pipeline=GroupPipeline(client,fetch,require_ocr_response=True)
            group=items(row('Mầm non Hoa Hồng'),row('Mầm non Hoa Mai'))
            def queued_tasks():
                return [json.loads(p.read_text())['body']['text']['format']['name']
                        for p in Path(tmp).glob('*.request.json')]
            with self.assertRaises(NeedsBatch):pipeline.process_group(group)
            self.assertEqual(queued_tasks(),['observe']);self.assertEqual(fetch.pages,0)
            job=store.prepare();self.assertFalse(store.submit_or_poll(job,api))
            with self.assertRaises(NeedsBatch):pipeline.process_group(group)
            self.assertEqual(queued_tasks(),['observe']);self.assertEqual(fetch.pages,0)
            api.pending=False;self.assertTrue(store.submit_or_poll(job,api))
            with self.assertRaises(NeedsBatch):pipeline.process_group(group)
            self.assertCountEqual(queued_tasks(),['observe','group_source_address_v2'])
            self.assertEqual(fetch.pages,1)

    def test_invalid_ocr_response_blocks_source_and_preserves_blanks(self):
        from grouped_pipeline import GroupPipeline
        from test_grouped_pipeline import items
        class InvalidOCR(FakeAPI):
            def content(self,key):
                item=json.loads(super().content(key))
                item['response']['body']['output'][0]['content'][0]['text']='invalid JSON'
                return json.dumps(item).encode()
        with tempfile.TemporaryDirectory() as tmp:
            store=self.make(tmp);client=BatchModelClient(store);fetch=Fetch()
            pipeline=GroupPipeline(client,fetch,require_ocr_response=True)
            group=items(row('Mầm non Hoa Hồng'),row('Mầm non Hoa Mai'))
            with self.assertRaises(NeedsBatch):pipeline.process_group(group)
            store.submit_or_poll(store.prepare(),InvalidOCR())
            result=pipeline.process_group(group)
            self.assertEqual([r['approve'] for r in result],['',''])
            self.assertEqual(fetch.pages,0)
            self.assertEqual(store.report()['batch_requests'],1)
            self.assertGreater(store.report()['charged_or_reserved_usd'],0)
            self.assertTrue(all(r['errors'][0]['error']=='BATCH_INVALID_JSON' for r in result))

    def test_two_dependent_stages_and_full_resume_keep_main_unchanged(self):
        import csv
        import run_grouped_luna as runner
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);out=root/'outputs/run';source=root/'main.csv'
            rows=[row('Mầm non Hoa Hồng'),row('Mầm non Hoa Mai')]
            with source.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            before=source.read_bytes()
            for name in ('run_grouped_luna.py','grouped_pipeline.py','grouped_user_rules.py','address_rules.py','api_economy.py','api_providers.py',
                         'approve_tool.py','matching.py','source_page.py','batch_api.py','grouped_batch.py','name_overrides.json'):
                shutil.copy2(ROOT/name,root/name)
            args=SimpleNamespace(input=source,output_dir=out,model='gpt-6-luna',start_row=1,first=1,
                workers=2,budget_usd=1,save_every=1,run=True,resume=False,execution='batch',
                watch=False,poll_seconds=1,batch_requests=500,batch_mb=50)
            api=FakeAPI();api.pending=True
            with patch.object(runner,'ROOT',root),patch.dict(os.environ,{'OPENAI_API_KEY':'fake'}),patch('sys.stdout',new_callable=io.StringIO):
                self.assertEqual(runner.run(args,fetcher_factory=lambda *a:Fetch(),batch_api_factory=lambda *a:api),0)
                summary=json.loads((out/'summary.json').read_text());self.assertFalse(summary['complete'])
                self.assertEqual(summary['stop_reason'],'WAITING_BATCH')
                args.resume=True;api.pending=False
                self.assertEqual(runner.run(args,fetcher_factory=lambda *a:Fetch(),batch_api_factory=lambda *a:api),0)
                self.assertEqual(api.creates,2)
                summary=json.loads((out/'summary.json').read_text());self.assertTrue(summary['complete'])
                self.assertEqual(summary['counts'],{'no':1,'yes':1})
                self.assertEqual(runner.run(args,fetcher_factory=lambda *a:Fetch(),batch_api_factory=lambda *a:api),0)
                self.assertEqual(api.creates,2)
            self.assertEqual(source.read_bytes(),before)

if __name__=='__main__':unittest.main()
