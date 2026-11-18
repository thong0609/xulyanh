import csv
import io
import json
import os
from pathlib import Path
import shutil
import sys,tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from approve_tool import ROOT
from batch_api import BatchStore,BatchModelClient,NeedsBatch
from test_batch_api import FakeAPI
from test_grouped_pipeline import Fetch,row
from test_grouped_user_rules import answer
import run_grouped_luna as runner


class ControlledAPI(FakeAPI):
    def __init__(self):super().__init__();self.complete_ids=set();self.complete_all=False
    def get(self,bid):
        if not self.complete_all and bid not in self.complete_ids:return dict(self.jobs[bid])
        raw=super().get(bid)
        tasks={json.loads(line)['custom_id']:json.loads(line)['body']['text']['format']['name']
               for line in self.files[raw['input_file_id']].splitlines()}
        values=[json.loads(line) for line in self.files[raw['output_file_id']].splitlines()]
        for item in values:
            if tasks[item['custom_id']]=='group_source_user_rules_v4':
                item['response']['body']['output'][0]['content'][0]['text']=json.dumps(answer(winner='R0'))
        self.files[raw['output_file_id']]=b'\n'.join(json.dumps(v).encode() for v in values)
        return raw
    def task_batches(self,task):
        return [bid for bid,job in self.jobs.items() if any(
            json.loads(line)['body']['text']['format']['name']==task
            for line in self.files[job['input_file_id']].splitlines())]


class ParallelBatchTests(unittest.TestCase):
    def test_prepared_jobs_claim_disjoint_keys_even_before_submission_and_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=BatchStore(tmp,'gpt-6-luna',1,.0625,.25);client=BatchModelClient(store)
            for i in range(9):
                with self.assertRaises(NeedsBatch):client.observe(str(i).encode())
            jobs=[store.prepare(max_requests=1,allow_multiple=True) for _ in range(8)]
            keys=[k for j in jobs for k in j['keys']]
            self.assertEqual(len(set(keys)),8)
            restored=BatchStore(tmp,'gpt-6-luna',1,.0625,.25)
            ninth=restored.prepare(max_requests=1,allow_multiple=True)
            self.assertNotIn(ninth['keys'][0],keys)
            self.assertIsNone(restored.prepare(max_requests=1,allow_multiple=True))
            self.assertEqual(restored.prepare(),restored.state['jobs'][0])

    def test_eight_active_jobs_partial_completion_source_overlap_resume_and_no_duplicate_create(self):
        class DistinctImages(Fetch):
            def image(self,url):return url.encode()
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);out=root/'outputs/run';source=root/'main.csv'
            rows=[row('Candidate '+str(i),url=f'https://images.test/{i}.jpg') for i in range(9)]
            with source.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            before=source.read_bytes()
            for name in ('run_grouped_luna.py','grouped_pipeline.py','grouped_user_rules.py','address_rules.py',
                         'api_economy.py','api_providers.py','approve_tool.py','matching.py','source_page.py',
                         'batch_api.py','grouped_batch.py','name_overrides.json'):
                shutil.copy2(ROOT/name,root/name)
            args=SimpleNamespace(input=source,output_dir=out,model='gpt-6-luna',start_row=1,first=9,
                workers=3,budget_usd=1,save_every=1,run=True,resume=False,execution='batch',policy='user-rules-v4',
                watch=False,poll_seconds=1,batch_requests=1,batch_mb=50,max_active_batches=8)
            api=ControlledAPI()
            def invoke():return runner.run(args,fetcher_factory=lambda *a:DistinctImages(),batch_api_factory=lambda *a:api)
            with patch.object(runner,'ROOT',root),patch.dict(os.environ,{'OPENAI_API_KEY':'fake'}),patch('sys.stdout',new_callable=io.StringIO):
                self.assertEqual(invoke(),0);self.assertEqual(api.creates,8)
                summary=json.loads((out/'summary.json').read_text())
                self.assertEqual(summary['active_batches'],8);self.assertEqual(summary['remaining'],9)
                self.assertEqual(api.task_batches('group_source_user_rules_v4'),[])
                args.resume=True
                self.assertEqual(invoke(),0);self.assertEqual(api.creates,8)
                api.complete_ids={'batch1','batch2'}
                self.assertEqual(invoke(),0)
                # The source stage for a completed OCR begins while other OCR jobs remain pending.
                source_batches=api.task_batches('group_source_user_rules_v4')
                self.assertEqual(len(source_batches),1)
                self.assertTrue(any(j['status']=='in_progress' for bid,j in api.jobs.items() if bid not in api.complete_ids))
                self.assertEqual(api.creates,10)
                api.complete_ids.add(source_batches[0]);self.assertEqual(invoke(),0)
                summary=json.loads((out/'summary.json').read_text());self.assertEqual(summary['completed'],1)
                self.assertLessEqual(summary['active_batches'],8)
                api.complete_all=True;self.assertEqual(invoke(),0)
                summary=json.loads((out/'summary.json').read_text());self.assertTrue(summary['complete'])
                self.assertEqual(summary['counts'],{'yes':9});self.assertEqual(summary['active_batches'],0)
                creates=api.creates;args.max_active_batches=6
                self.assertEqual(invoke(),0);self.assertEqual(api.creates,creates)
            state=json.loads((out/'batch/state.json').read_text())
            all_keys=[key for job in state['jobs'] for key in job['keys']]
            self.assertEqual(len(all_keys),len(set(all_keys)));self.assertEqual(len(all_keys),18)
            self.assertEqual(source.read_bytes(),before)

    def test_source_priority_with_legacy_state_and_existing_ocr_job(self):
        from approve_tool import schema,TEXT
        with tempfile.TemporaryDirectory() as tmp:
            store=BatchStore(tmp,'gpt-6-luna',1,.0625,.25);client=BatchModelClient(store)
            for im in (b'first',b'second',b'third'):
                with self.assertRaises(NeedsBatch):client.observe(im)
            first=store.prepare(max_requests=1,allow_multiple=True)
            original_keys=list(first['keys'])
            with self.assertRaises(NeedsBatch):client.ask('group_source_user_rules_v4','test',{},schema({'winner_id':TEXT}))
            source_key=next(k for k,v in store.state['requests'].items() if 'winner_id' in v['schema']['properties'])
            before=store.report()['charged_or_reserved_usd']
            for entry in store.state['requests'].values():entry.pop('task',None)
            store.save();restored=BatchStore(tmp,'gpt-6-luna',1,.0625,.25)
            second=restored.prepare(max_requests=2,allow_multiple=True)
            self.assertEqual(second['keys'][0],source_key)
            self.assertEqual(restored.state['jobs'][0]['keys'],original_keys)
            self.assertTrue(set(original_keys).isdisjoint(second['keys']))
            self.assertEqual(restored.report()['charged_or_reserved_usd'],before)
            self.assertEqual(restored.report()['queued_source_requests'],0)
            self.assertEqual(restored.report()['queued_ocr_requests'],1)

    def test_scheduler_upgrade_pins_both_hashes_and_preserves_policy(self):
        upgrades=json.loads((ROOT/'batch_runtime_compatibility.json').read_text())
        old={'code_sha256':upgrades[-1]['from'],'budget_usd':3,'workers':8,
             'max_active_batches':8,'decision_policy':'user-rules-v4','input_sha256':'same'}
        current=dict(old,code_sha256=upgrades[-1]['to'])
        self.assertTrue(runner.batch_runtime_compatible(old,current))
        self.assertFalse(runner.batch_runtime_compatible(old,dict(current,decision_policy='legacy')))
        self.assertFalse(runner.batch_runtime_compatible(old,dict(current,code_sha256='unreviewed')))
        self.assertFalse(runner.batch_runtime_compatible(old,dict(current,budget_usd=1)))

    def test_cli_accepts_six_and_eight_and_rejects_more(self):
        for n in (6,8):
            with patch.object(runner,'run',return_value=0) as mocked:
                self.assertEqual(runner.main(['--max-active-batches',str(n)]),0)
            self.assertEqual(mocked.call_args.args[0].max_active_batches,n)
        from approve_tool import CheckError
        with self.assertRaises(CheckError):runner.main(['--max-active-batches','9'])

if __name__=='__main__':unittest.main()
