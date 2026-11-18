import csv
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from approve_tool import ROOT,CheckError,read_csv
import run_grouped_luna as runner
sys.path.insert(0,str(ROOT/'kaggle'))
from compare_runs import compare


class GroupedPilotTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'input.csv'
        fields=['entity_id','entity_name','image_url','page_url','approve']
        rows=[['A','Alpha','first.jpg','https://x.test/',''],
              ['B','Beta','shared.jpg','https://x.test/',''],
              ['C','Gamma','shared.jpg','https://x.test/','']]
        with source.open('w',newline='') as f:
            w=csv.writer(f);w.writerow(fields);w.writerows(rows)
        _,_,ids,_,_,sha=read_csv(source)
        left=root/'baseline';left.mkdir();right=root/'candidate';right.mkdir()
        for folder,selection,seed in ((left,[1],None),(right,[1,2],[1])):
            manifest={'input_sha256':sha,'selected_indices':selection}
            if seed is not None:manifest['seed_indices']=seed
            (folder/'manifest.json').write_text(json.dumps(manifest))
            (folder/'results.jsonl').write_text(''.join(json.dumps({'row_index':i,'row_id':ids[i],
                'approve':'yes' if i==1 else 'no','reason':'test'})+'\n' for i in selection))
        return source,left,right

    def test_baseline_chooses_original_noncontiguous_seed_and_expands_group(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);source,left,right=self.fixture(root)
            for name in ('run_grouped_luna.py','grouped_pipeline.py','grouped_user_rules.py','address_rules.py','api_economy.py','api_providers.py',
                         'approve_tool.py','matching.py','source_page.py','batch_api.py','grouped_batch.py','name_overrides.json'):
                shutil.copy2(ROOT/name,root/name)
            args=SimpleNamespace(input=source,output_dir=root/'outputs/test',baseline_dir=left,model='gpt-6-luna',
                execution='batch',first=2000,start_row=1,workers=1,budget_usd=1,run=False,resume=False)
            before=source.read_bytes()
            with patch.object(runner,'ROOT',root),patch('sys.stdout',new_callable=io.StringIO):
                self.assertEqual(runner.run(args),0)
            manifest=json.loads((args.output_dir/'selection_preview.json').read_text())['manifest']
            self.assertEqual(manifest['seed_indices'],[1])
            self.assertEqual(manifest['selected_indices'],[1,2])
            self.assertEqual(source.read_bytes(),before)

    def test_expanded_compare_requires_flag_and_compares_only_pilot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,left,right=self.fixture(root)
            with self.assertRaises(CheckError):compare(source,left,right,root/'bad')
            with patch('sys.stdout',new_callable=io.StringIO):
                path=compare(source,left,right,root/'comparison',baseline_rows=True)
            with path.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['entity_id'],'B')
            summary=json.loads((path.parent/'comparison_summary.json').read_text())
            self.assertEqual(summary['candidate_selected'],2)

    def test_compare_rejects_wrong_seed_or_incomplete_expanded_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,left,right=self.fixture(root)
            m=json.loads((right/'manifest.json').read_text());m['seed_indices']=[2]
            (right/'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(CheckError):compare(source,left,right,root/'bad',baseline_rows=True)
            m['seed_indices']=[1];(right/'manifest.json').write_text(json.dumps(m))
            lines=(right/'results.jsonl').read_text().splitlines()
            (right/'results.jsonl').write_text(lines[0]+'\n')
            with self.assertRaises(CheckError):compare(source,left,right,root/'bad',baseline_rows=True)

if __name__=='__main__':unittest.main()
