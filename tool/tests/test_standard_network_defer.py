import csv,io,json,os,shutil,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from approve_tool import ROOT
from api_providers import ProviderFatal
from test_grouped_pipeline import Model,Fetch,row
from test_grouped_user_rules import answer
import run_grouped_luna_standard as runner


class StandardNetworkDeferTests(unittest.TestCase):
    def scenario(self,error):
        class Distinct(Fetch):
            def image(self,url):return url.encode()
        class Flaky(Model):
            broken=True
            def __init__(self):super().__init__(answer(winner='R0'));self.bad_attempts=0
            def observe(self,image):
                if image.endswith(b'/0.jpg'):
                    self.bad_attempts+=1
                    if self.broken:raise ProviderFatal(error)
                return super().observe(image)
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);source=root/'source.csv';out=root/'outputs/run'
            rows=[row('Candidate '+str(i),url=f'https://img.test/{i}.jpg') for i in range(3)]
            with source.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            before=source.read_bytes()
            for name in ('run_grouped_luna_standard.py','grouped_pipeline.py','grouped_user_rules.py','address_rules.py',
                         'api_economy.py','api_providers.py','approve_tool.py','matching.py','source_page.py','name_overrides.json'):
                shutil.copy2(ROOT/name,root/name)
            args=SimpleNamespace(input=source,output_dir=out,model='gpt-6-luna',execution='standard',
                start_row=1,first=3,workers=1,budget_usd=1,run=True,resume=False,policy='user-rules-v4',save_every=1)
            model=Flaky()
            with patch.object(runner,'ROOT',root),patch.dict(os.environ,{'OPENAI_API_KEY':'fake'}),patch('sys.stdout',new_callable=io.StringIO):
                self.assertEqual(runner.run(args,client_factory=lambda *a,**kw:model,fetcher_factory=lambda *a:Distinct()),2)
                first=json.loads((out/'summary.json').read_text());self.assertEqual(model.bad_attempts,1)
                if error=='API_NETWORK_ERROR':
                    self.assertEqual(first['completed'],2)
                    self.assertEqual(first['network_deferred_groups'],1)
                    self.assertEqual(first['stop_reason'],'NETWORK_GROUPS_PENDING_RESUME')
                    self.assertEqual(first['counts'],{'yes':2})
                    healthy_calls=model.calls;model.broken=False;args.resume=True
                    self.assertEqual(runner.run(args,client_factory=lambda *a,**kw:model,fetcher_factory=lambda *a:Distinct()),0)
                    final=json.loads((out/'summary.json').read_text());self.assertTrue(final['complete'])
                    self.assertEqual(final['counts'],{'yes':3});self.assertEqual(model.calls,healthy_calls+1)
                else:
                    self.assertEqual(first['completed'],0);self.assertEqual(first['stop_reason'],error)
                    self.assertEqual(first['network_deferred_groups'],0)
            self.assertEqual(source.read_bytes(),before)
    def test_network_error_defers_only_its_group_and_resume_recovers_it(self):self.scenario('API_NETWORK_ERROR')
    def test_auth_failure_still_stops_the_run(self):self.scenario('API_HTTP_401')

if __name__=='__main__':unittest.main()
