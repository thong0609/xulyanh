"""Offline regression tests for batching, OOM isolation and concurrent row identity."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'kaggle'))
import gpu_backend as gpu
import run_gpu as runner
from approve_tool import OCR_SCHEMA, CheckError


class Tensor:
    def __init__(self, values): self.values = values
    @property
    def shape(self): return (len(self.values), len(self.values[0]))
    def __getitem__(self, key):
        rows, cols = key
        return Tensor([r[cols] for r in self.values[rows]])
    def sum(self, dim): return Tensor([sum(r) for r in self.values])
    def tolist(self): return self.values
    def cpu(self): return self


class Inputs(dict):
    def to(self, device): return self


class Processor:
    def apply_chat_template(self, messages, **kw): return messages
    def __call__(self, text, images, **kw):
        return Inputs(input_ids=Tensor([[1, 2, 3]]*len(text)),
                      attention_mask=Tensor([[1, 1, 1]]*len(text)))
    def batch_decode(self, tokens, **kw):
        return [json.dumps({'status':'readable', 'texts':[str(t[0])]}) for t in tokens]


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.c = gpu.QwenClient.__new__(gpu.QwenClient)
        c = self.c
        c.cache = Path(self.tmp.name)
        c.identity = {'test':True}
        c.condition = threading.Condition()
        c.pending, c.inflight = [], {}
        c.closed, c.fatal = False, None
        c.batch_size, c.batch_wait, c.batch_token_budget = 2, .05, 8192
        c.calls = c.cache_hits = c.input_tokens = c.output_tokens = 0
        c.seconds = c.preprocess_seconds = c.generate_seconds = c.queue_wait_seconds = 0.
        c.oom_retries = c.budget_splits = 0
        c.batch_counts = Counter()
        c.max_input_tokens, c.max_new_tokens = 4096, 4
        c.load_seconds = 0.
        c.processor = Processor()
        class OOM(RuntimeError): pass
        c.torch = SimpleNamespace(cuda=SimpleNamespace(OutOfMemoryError=OOM,
            synchronize=lambda:None, empty_cache=lambda:None), inference_mode=nullcontext)
        c.model = SimpleNamespace(generation_config=SimpleNamespace(eos_token_id=9))

    def tearDown(self):
        if hasattr(self.c, 'worker'): self.c.close()
        self.tmp.cleanup()

    def start(self):
        self.c.worker = threading.Thread(target=self.c._worker, daemon=True)
        self.c.worker.start()

    def request(self, i):
        return dict(data={}, schema=OCR_SCHEMA, instruction='', image=None,
                    path=self.c.cache/f'{i}.json')

    def test_two_requests_share_batch_and_return_to_correct_callers(self):
        seen = []
        def infer(batch):
            seen.append([r['data']['id'] for r in batch])
            return [{'id':r['data']['id']} for r in batch]
        self.c._infer = infer
        self.start()
        with ThreadPoolExecutor(2) as pool:
            fs = [pool.submit(self.c.ask, 'ocr', '', {'id':i}, OCR_SCHEMA) for i in range(2)]
            self.assertEqual([f.result(timeout=3) for f in fs], [{'id':0}, {'id':1}])
        self.assertEqual(seen, [[0, 1]])

    def test_different_modalities_never_share_batch(self):
        seen = []
        def infer(batch):
            seen.append([bool(r['image']) for r in batch])
            return [{} for r in batch]
        self.c._infer = infer
        self.start()
        with ThreadPoolExecutor(2) as pool:
            fs = [pool.submit(self.c.ask, 'task', '', {'id':i}, OCR_SCHEMA, image)
                  for i,image in enumerate([None, b'image'])]
            for f in fs: f.result(timeout=3)
        self.assertEqual(seen, [[False], [True]])

    def test_oom_splits_then_remembers_lower_batch_size(self):
        self.c._infer = lambda b: 'oom' if len(b)>1 else [{'id':b[0]}]
        self.assertEqual(self.c._execute([10, 20]), [{'id':10}, {'id':20}])
        self.assertEqual(self.c.batch_size, 1)
        self.assertEqual(self.c.oom_retries, 1)

    def test_fatal_wakes_current_queued_and_later_callers(self):
        self.c._infer = lambda b: 'oom'
        self.start()
        with ThreadPoolExecutor(4) as pool:
            fs = [pool.submit(self.c.ask, str(i), '', {'id':i}, OCR_SCHEMA) for i in range(4)]
            for f in fs:
                with self.assertRaises(gpu.FatalGPUError): f.result(timeout=3)
        with self.assertRaises(gpu.FatalGPUError): self.c.ask('later', '', {}, OCR_SCHEMA)

    def test_single_request_does_not_wait_for_full_batch_forever(self):
        self.c._infer = lambda b: [{} for _ in b]
        self.start()
        with ThreadPoolExecutor(1) as pool:
            self.assertEqual(pool.submit(self.c.ask, 'one', '', {}, OCR_SCHEMA).result(timeout=3), {})

    def test_batched_eos_and_padding_are_handled_per_record(self):
        def generate(**kw):
            self.assertEqual(kw['logits_to_keep'], 1)
            return Tensor([[1,2,3,11,9,0,0], [1,2,3,22,23,24,9]])
        self.c.model.generate = generate
        values = self.c._infer([self.request(0), self.request(1)])
        self.assertEqual([v['texts'] for v in values], [['11'], ['22']])
        self.assertEqual(self.c.output_tokens, 6)
        self.assertEqual(self.c.batch_counts, {2:1})

    def test_output_limit_only_rejects_unfinished_row(self):
        self.c.model.generate = lambda **kw: Tensor([[1,2,3,11,9,0,0], [1,2,3,22,23,24,25]])
        values = self.c._infer([self.request(0), self.request(1)])
        self.assertEqual(values[0]['texts'], ['11'])
        self.assertIsInstance(values[1], CheckError)
        self.assertEqual(str(values[1]), 'LOCAL_OUTPUT_LIMIT')

    def test_long_request_does_not_reject_short_neighbor(self):
        self.c.max_input_tokens = 4
        class VariableProcessor(Processor):
            def __call__(self, text, images, **kw):
                n = max(json.loads(p[1]['content'][-1]['text'])['length'] for p in text)
                return Inputs(input_ids=Tensor([[1]*n]*len(text)),
                              attention_mask=Tensor([[1]*n]*len(text)))
        self.c.processor = VariableProcessor()
        self.c.model.generate = lambda **kw: Tensor([row+[11,9] for row in kw['input_ids'].values])
        requests = [self.request(0), self.request(1)]
        requests[0]['data'] = {'length':3}
        requests[1]['data'] = {'length':10}
        values = self.c._execute(requests)
        self.assertEqual(values[0]['texts'], ['11'])
        self.assertEqual(str(values[1]), 'LOCAL_CONTEXT_TOO_LONG')

    def test_bounded_parallel_records_keep_identity(self):
        barrier = threading.Barrier(3)
        lock = threading.Lock()
        active = peak = 0
        def process(i):
            nonlocal active, peak
            with lock: active += 1; peak = max(peak, active)
            barrier.wait(timeout=3)
            time.sleep(.005*(3-i%3))
            with lock: active -= 1
            return {'row_index':i}
        results = [(i, f.result()) for i,f in runner.concurrent_rows(range(9), process, 3, lambda:False)]
        self.assertEqual(peak, 3)
        self.assertEqual(sorted(i for i,_ in results), list(range(9)))
        self.assertTrue(all(i==r['row_index'] for i,r in results))


if __name__ == '__main__': unittest.main()
