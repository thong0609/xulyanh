import io
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_grouped_pilot as pilot_tests
from test_grouped_pipeline import Model,Fetch,decision
from approve_tool import ROOT,CheckError
import run_grouped_luna_standard as runner


class StandardTests(unittest.TestCase):
    def test_unicode_fetch_and_model_failures_become_check_errors(self):
        error=UnicodeEncodeError('ascii','đ',0,1,'unsupported')
        with patch.object(runner.ResilientFetcher,'fetch',side_effect=error):
            fetch=runner.StandardFetcher.__new__(runner.StandardFetcher)
            with self.assertRaisesRegex(CheckError,'FETCH_URL_ENCODING_ERROR'):fetch.fetch('https://x.test','page')
        with patch.object(runner.EconomyClient,'ask',side_effect=error):
            client=runner.StandardClient.__new__(runner.StandardClient)
            with self.assertRaisesRegex(CheckError,'MODEL_UNICODE_ENCODING_ERROR'):client.ask('task')

    def test_runtime_upgrade_pins_both_hashes_and_rejects_policy_changes(self):
        upgrades=json.loads((ROOT/'standard_runtime_compatibility.json').read_text())
        old={'code_sha256':upgrades[0]['from'],'budget_usd':3,'workers':8,'input_sha256':'same','first':2000}
        new=dict(old,code_sha256=upgrades[0]['to'])
        self.assertTrue(runner.runtime_compatible(old,new))
        self.assertFalse(runner.runtime_compatible(old,dict(new,code_sha256='unreviewed')))
        self.assertFalse(runner.runtime_compatible(old,dict(new,first=50)))
        self.assertFalse(runner.runtime_compatible(old,dict(new,budget_usd=1)))

    def test_unlabeled_selection_skips_labels_and_expands_past_seed(self):
        from grouped_pipeline import image_groups
        rows=[{'approve':label,'image_url':image} for label,image in
              [('yes','old'),('','shared'),('no','shared'),('','other'),('','shared')]]
        seed=runner.select_seed(rows,1,2,unlabeled_only=True)
        self.assertEqual(seed,[1,3])
        selected,groups=image_groups(rows,seed)
        self.assertEqual(selected,[1,2,3,4])
        self.assertEqual(runner.select_seed(rows,3,2,unlabeled_only=True),[3,4])
        self.assertEqual(runner.select_seed(rows,1,2),[0,1])

    def run_fixture(self,model,policy='legacy'):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);source,baseline,_=pilot_tests.GroupedPilotTests().fixture(root)
            for name in ('run_grouped_luna_standard.py','grouped_pipeline.py','grouped_user_rules.py','address_rules.py','api_economy.py',
                         'api_providers.py','approve_tool.py','matching.py','source_page.py','name_overrides.json'):
                shutil.copy2(ROOT/name,root/name)
            args=SimpleNamespace(input=source,baseline_dir=baseline,output_dir=root/'outputs/standard',
                execution='standard',policy=policy,model='gpt-6-luna',first=2000,start_row=1,workers=2,budget_usd=1,
                save_every=1,run=True,resume=False)
            before=source.read_bytes();fetch=Fetch('Gamma')
            with patch.object(runner,'ROOT',root),patch.dict(os.environ,{'OPENAI_API_KEY':'fake'}),patch('sys.stdout',new_callable=io.StringIO):
                self.assertEqual(runner.run(args,client_factory=lambda *a,**kw:model,fetcher_factory=lambda *a:fetch),0)
                args.resume=True
                self.assertEqual(runner.run(args,client_factory=lambda *a,**kw:model,fetcher_factory=lambda *a:fetch),0)
            self.assertEqual(source.read_bytes(),before)
            self.assertFalse((args.output_dir/'batch').exists())
            manifest=json.loads((args.output_dir/'manifest.json').read_text())
            self.assertEqual(manifest['execution'],'standard');self.assertEqual(manifest['seed_indices'],[1])
            summary=json.loads((args.output_dir/'summary.json').read_text())
            self.assertEqual(summary['billing_mode'],'standard');self.assertTrue(summary['complete'])
            return summary,fetch
    def test_v4_standard_runner_model_winner_without_evidence(self):
        from test_grouped_user_rules import answer
        model=Model(answer(winner='R1'))
        summary,fetch=self.run_fixture(model,policy='user-rules-v4')
        self.assertEqual(summary['counts'],{'no':1,'yes':1})
        self.assertEqual((model.ocr,model.calls),(1,1))

    def test_cli_defaults_to_v5(self):
        with patch.object(runner,'run',return_value=0) as mocked:
            self.assertEqual(runner.main([]),0)
        self.assertEqual(mocked.call_args.args[0].policy,'user-rules-v5')

    def test_standard_grouped_runner_and_resume(self):
        model=Model(decision(winner='R1',subject='Gamma'))
        summary,fetch=self.run_fixture(model)
        self.assertEqual(summary['counts'],{'no':1,'yes':1})
        self.assertEqual((model.ocr,model.calls),(1,1))
    def test_ocr_error_never_calls_source(self):
        class Invalid(Model):
            def observe(self,image):raise CheckError('OCR_FAILED')
        model=Invalid();summary,fetch=self.run_fixture(model)
        self.assertEqual(summary['counts'],{'blank':2})
        self.assertEqual(fetch.pages,0);self.assertEqual(model.calls,0)

if __name__=='__main__':unittest.main()
