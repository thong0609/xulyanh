import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL/'kaggle'))
import gpu_backend as gpu
import run_gpu as runner
from restore import restore
import package as packaging
from approve_tool import CheckError, MATCH_SCHEMA, OCR_SCHEMA


class FakeGPU:
    fail_after = None
    def __init__(self, *a, **kw):
        self.identity = {'revision': 'pinned-test-sha'}
        self.n = 0
    def observe(self, image):
        self.n += 1
        if self.fail_after is not None and self.n > self.fail_after:
            raise gpu.FatalGPUError('TEST_GPU_OOM')
        return {'status':'no_text','texts':[]}
    def compare(self, profile, texts, context): return {'status':'not_match','evidence':'','explanation':''}
    def assess_page(self, profile, page): return {'status':'name_not_found','evidence':'','context_index':-1}
    def report(self): return {'local_generation_calls':self.n,'paid_api_calls':0}


class FakeFetch:
    def __init__(self, *a): pass
    def image(self, url): return b'fake'
    def page(self, *a): return {'incomplete':False,'truncated':False,'text':'nội dung','contexts':[]}


class GPUJsonTests(unittest.TestCase):
    def test_valid_and_fenced(self):
        obj={'status':'not_match','evidence_ids':[], 'observed_name':'',
             'name_relation':'not_applicable','explanation':'không thấy'}
        for text in [json.dumps(obj), '```json\n'+json.dumps(obj)+'\n```']:
            self.assertEqual(gpu.parse_result(text,MATCH_SCHEMA),obj)

    def test_invalid_or_invented_fields_rejected(self):
        for obj in [{'status':'match'}, {'status':'no_text','texts':'string'},
                    {'status':'readable','texts':[],'extra':True}, {'status':'guess','texts':[]}]:
            with self.assertRaises(CheckError): gpu.parse_result(json.dumps(obj),OCR_SCHEMA)
        with self.assertRaises(CheckError): gpu.parse_result('Here is JSON: {}',OCR_SCHEMA)

    def test_no_paid_fallback(self):
        client=gpu.QwenClient.__new__(gpu.QwenClient)
        with self.assertRaises(RuntimeError):client._post({})


class GPURunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=TOOL)
        self.root=Path(self.tmp.name)
        self.source=self.root/'source.csv'
        self.rows=[{'entity_id':str(i),'entity_name':'Mầm non Hoa Hồng',
                    'image_url':'https://example.org/photo.jpg','page_url':'https://example.org/post',
                    'leaf_label':'Trường', 'mo_ta':'must stay unchanged',
                    'approve':'yes' if i==0 else ''} for i in range(12)]
        with self.source.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(self.rows[0]));w.writeheader();w.writerows(self.rows)
        self.before=self.source.read_bytes()
        self.work=self.root/'work'
        self.args=runner.parser().parse_args(['--input',str(self.source),'--work-dir',str(self.work),
                                             '--all','--workers','1','--min-free-gb','.001','--save-every','2',
                                             '--bundle-every','3'])
        self.output=self.work/'outputs/full_gpu'
        self.silent=patch('sys.stdout',new_callable=io.StringIO);self.silent.start()
    def tearDown(self):
        self.silent.stop();self.tmp.cleanup()

    def run_fake(self,args=None,client=FakeGPU):
        return runner.run(args or self.args,client_factory=client,fetcher_factory=FakeFetch)

    def test_full_export_and_resume(self):
        self.assertEqual(self.run_fake(),0)
        summary=json.loads((self.output/'summary.json').read_text())
        self.assertEqual(summary['completed'],11)
        self.assertEqual(summary['counts'],{'no':11})
        self.assertEqual(summary['paid_api_calls'],0)
        with (self.output/'reviewed.csv').open(encoding='utf-8-sig',newline='') as f:actual=list(csv.DictReader(f))
        self.assertEqual(len(actual),12)
        for i,(before,after) in enumerate(zip(self.rows,actual)):
            self.assertEqual({k:v for k,v in before.items() if k!='approve'},
                             {k:v for k,v in after.items() if k!='approve'})
            self.assertEqual(after['approve'],'yes' if i==0 else 'no')
        with self.assertRaises(CheckError):self.run_fake()
        self.args.resume=True
        self.assertEqual(self.run_fake(client=lambda *a,**kw:self.fail('No pending rows, must not load GPU')),0)
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_parallel_export_and_resume_keep_row_identity(self):
        self.args.workers = 4
        self.assertEqual(self.run_fake(), 0)
        entries = [json.loads(line) for line in (self.output/'results.jsonl').read_text().splitlines()]
        self.assertEqual(sorted(r['row_index'] for r in entries), list(range(1, 12)))
        self.assertEqual(len({r['row_id'] for r in entries}), 11)
        summary = json.loads((self.output/'summary.json').read_text())
        self.assertEqual(summary['counts'], {'no':11})
        self.assertGreater(summary['sessions'][-1]['rows_per_hour_excluding_load'], 0)
        self.args.resume = True
        self.assertEqual(self.run_fake(), 0)
        self.assertEqual(len((self.output/'results.jsonl').read_text().splitlines()), 11)

    def test_oom_checkpoint_restore_and_resume(self):
        class FailGPU(FakeGPU):fail_after=3
        self.assertEqual(self.run_fake(client=FailGPU),2)
        summary=json.loads((self.output/'summary.json').read_text())
        self.assertEqual(summary['completed'],3)
        self.assertFalse(summary['complete'])
        bundle=self.output/'resume_bundle.zip'
        with zipfile.ZipFile(bundle) as z:
            names=z.namelist()
            self.assertFalse(any('cache' in n or '.env' in n for n in names))
        new_work=self.root/'new-session'
        restore(bundle,new_work)
        self.args.work_dir=new_work;self.args.resume=True
        self.assertEqual(self.run_fake(),0)
        lines=(new_work/'outputs/full_gpu/results.jsonl').read_text().splitlines()
        self.assertEqual(len(lines),11)
        self.assertEqual(len({json.loads(x)['row_id'] for x in lines}),11)

    def test_truncated_last_journal_recovers(self):
        class FailGPU(FakeGPU):fail_after=2
        self.run_fake(client=FailGPU)
        with (self.output/'results.jsonl').open('ab') as f:f.write(b'{"partial":')
        self.args.resume=True
        self.assertEqual(self.run_fake(),0)
        self.assertEqual(len((self.output/'results.jsonl').read_text().splitlines()),11)

    def test_input_and_config_changes_rejected(self):
        self.run_fake();self.args.resume=True
        self.args.max_pixels+=784
        with self.assertRaises(CheckError):self.run_fake()
        self.args.max_pixels-=784
        self.source.write_bytes(self.before+b'\n')
        with self.assertRaises(CheckError):self.run_fake()

    def test_first_rows_filters_labels_without_refill(self):
        self.args.all=False;self.args.first=4;self.args.prepare_only=True
        self.assertEqual(self.run_fake(client=lambda *a,**kw:self.fail('GPU loaded')),0)
        actual=json.loads((self.output/'selection.json').read_text())
        self.assertEqual(actual['indices'],[1,2,3])
        self.assertEqual(actual['mode'],'first')
        self.args.first=0
        with self.assertRaises(CheckError):self.run_fake()

    def test_prepare_only_uses_no_gpu(self):
        self.args.prepare_only=True
        self.assertEqual(self.run_fake(client=lambda *a,**kw:self.fail('GPU loaded')),0)
        self.assertTrue((self.output/'selection.json').exists())
        self.assertFalse((self.output/'reviewed.csv').exists())

    def test_url_shortcut_never_calls_observe(self):
        self.rows[1]['page_url']='https://example.org/mam-non-hoa-hong'
        with self.source.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(self.rows[0]));w.writeheader();w.writerows(self.rows[:2])
        class CannotObserve(FakeGPU):
            def observe(self,*a):raise AssertionError('URL match should skip GPU')
        self.assertEqual(self.run_fake(client=CannotObserve),0)
        summary=json.loads((self.output/'summary.json').read_text())
        self.assertEqual(summary['counts'],{'yes':1})

    def test_restore_rejects_traversal_and_overwrite(self):
        bad=self.root/'bad.zip'
        with zipfile.ZipFile(bad,'w') as z:z.writestr('tool/outputs/../../escape','bad')
        with self.assertRaises(ValueError):restore(bad,self.work)
        self.run_fake()
        (self.output/'summary.json').write_text('newer data')
        with self.assertRaises(ValueError):restore(self.output/'resume_bundle.zip',self.work)


class PackagingTests(unittest.TestCase):
    def test_notebook_code_syntax(self):
        nb=json.loads((TOOL/'kaggle/approve_images.ipynb').read_text())
        self.assertEqual(nb['nbformat'],4)
        for cell in nb['cells']:
            if cell['cell_type']=='code':compile(''.join(cell['source']),'<notebook>','exec')

    def test_package_allowlist(self):
        with tempfile.TemporaryDirectory(dir=TOOL) as tmp:
            root=Path(tmp)
            for name in packaging.FILES+['input/general_10m_part_02_copy.csv']:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
            (root/'.env').write_text('TOP_SECRET_KEY')
            (root/'outputs').mkdir();(root/'outputs/private.json').write_text('private')
            with patch('sys.stdout',new_callable=io.StringIO):archive=packaging.build(root)
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(set(z.namelist()),{'tool/'+n for n in packaging.FILES+['input/general_10m_part_02_copy.csv']})
                self.assertFalse(any(b'TOP_SECRET' in z.read(n) for n in z.namelist()))


if __name__=='__main__':unittest.main()
