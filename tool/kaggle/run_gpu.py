#!/usr/bin/env python3
"""Full-dataset local GPU runner with bounded HTTP cache and portable checkpoints."""
import argparse
from contextlib import ExitStack
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import threading
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import time
import zipfile

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL))
from approve_tool import (CheckError, Pipeline, Fetcher, read_csv, select_sample,
                          atomic_json, digest, encoded, export_csv, run_lock, within)
from matching import exact_match, profile_name
from gpu_backend import QwenClient, DEFAULT_MODEL, FatalGPUError

RUN_VERSION = 'gpu-run-v2.2-fast2'


def code_hash():
    files = ['approve_tool.py', 'matching.py', 'source_page.py',
             'kaggle/run_gpu.py', 'kaggle/gpu_backend.py', 'kaggle/qwen_policy.py']
    return digest(encoded({f: digest((TOOL/f).read_bytes()) for f in files}))


def prepare_input(source, work):
    source = Path(source).resolve()
    target = work/'input'/source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    source_hash = digest(source.read_bytes())
    if target.exists():
        if digest(target.read_bytes()) != source_hash:
            raise CheckError('Bản copy khác nguồn; dùng work-dir mới, không ghi đè snapshot')
    elif target != source:
        temp = target.with_suffix(target.suffix+'.tmp')
        shutil.copyfile(source, temp)
        if digest(temp.read_bytes()) != source_hash:
            raise CheckError('Input thay đổi trong lúc copy')
        os.replace(temp, target)
    return target


def load_results(path, selected, ids):
    results = {}
    if not path.exists(): return results
    # Stream journal: do not load all full page evidence into RAM.
    with path.open('rb+') as f:
        while True:
            pos = f.tell(); line = f.readline()
            if not line: break
            if not line.endswith(b'\n'):
                f.seek(pos); f.truncate(); break
            r = json.loads(line); i = r['row_index']
            if i not in selected or r['row_id'] != ids[i] or r['approve'] not in ('yes', 'no', ''):
                raise CheckError('Checkpoint không khớp snapshot')
            if i in results: raise CheckError('Checkpoint có dòng lặp')
            results[i] = {'row_id': r['row_id'], 'row_index': i,
                          'approve': r['approve'], 'reason': r['reason']}
    return results


def compact_result(result):
    result = dict(result)
    checks = dict(result.get('checks', {}))
    page = checks.pop('page', None)
    if page:
        checks['page_metadata'] = {k: page.get(k) for k in
            ('page_url', 'target_found', 'incomplete', 'truncated', 'contexts_truncated')}
        decision = checks.get('page_match', {})
        index = decision.get('context_index', -1)
        if 0 <= index < len(page.get('contexts', [])):
            checks['matched_context'] = page['contexts'][index]
    result['checks'] = checks
    return result


def trim_http_cache(folder, max_bytes):
    if not folder.exists(): return
    files = list(folder.glob('*'))
    entries = [(p.stat().st_mtime, p, p.stat().st_size) for p in files if p.is_file()]
    total = sum(size for _, _, size in entries)
    for _, path, size in sorted(entries):
        if total <= max_bytes: break
        path.unlink(missing_ok=True); total -= size


def checkpoint_zip(work, output, snapshot):
    # Excludes .env, HF weights, model/HTTP caches and unrelated run directories.
    path = output/'resume_bundle.zip'
    fd, tmp = tempfile.mkstemp(dir=output, suffix='.zip.tmp'); os.close(fd)
    try:
        with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
            z.write(snapshot, 'tool/input/'+snapshot.name)
            for name in ('manifest.json', 'results.jsonl', 'summary.json', 'reviewed.csv', 'name_overrides.json'):
                p = output/name
                if p.exists(): z.write(p, 'tool/outputs/'+output.name+'/'+name)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return path


class TimedFetcher:
    """Bounded locks prevent same-URL cache writes racing; unrelated URLs overlap."""
    def __init__(self, delegate):
        self.delegate = delegate
        self.locks = [threading.Lock() for _ in range(64)]
        self.stats_lock = threading.Lock()
        self.seconds, self.calls = Counter(), Counter()

    def _call(self, kind, *args):
        with self.locks[hash(args[0]) % len(self.locks)]:
            start = time.monotonic()
            try: return getattr(self.delegate, kind)(*args)
            finally:
                with self.stats_lock:
                    self.seconds[kind] += time.monotonic()-start
                    self.calls[kind] += 1

    def image(self, url): return self._call('image', url)
    def page(self, url, image_url): return self._call('page', url, image_url)
    def trim(self, folder, max_bytes):
        # Each fetch holds exactly one stripe, so acquiring all stripes is deadlock-free.
        with ExitStack() as stack:
            for lock in self.locks: stack.enter_context(lock)
            trim_http_cache(folder, max_bytes)

    def report(self):
        with self.stats_lock:
            return {'fetch_and_parse_seconds_sum': {k: round(v, 2) for k,v in self.seconds.items()},
                    'fetch_calls': dict(self.calls)}


def concurrent_rows(indices, process, workers, stopped):
    """At most workers records in flight. Only the caller writes checkpoints."""
    indices = iter(indices)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='record') as pool:
        active = {}
        def fill():
            while len(active) < workers and not stopped():
                i = next(indices, None)
                if i is None: break
                active[pool.submit(process, i)] = i
        fill()
        try:
            while active:
                ready, _ = wait(active, timeout=1, return_when=FIRST_COMPLETED)
                for future in ready:
                    yield active.pop(future), future
                fill()
        finally:
            for future in active: future.cancel()
            # Running requests finish/cache safely before caller closes the GPU worker.


def run(args, client_factory=QwenClient, fetcher_factory=Fetcher):
    if args.first is not None and args.first <= 0: raise CheckError('--first phải lớn hơn 0')
    work = args.work_dir.resolve()
    if Path('/kaggle').exists() and not work.is_relative_to('/kaggle/working'):
        raise CheckError('Trên Kaggle, work-dir phải nằm trong /kaggle/working')
    work.mkdir(parents=True, exist_ok=True)
    if not args.run_name or not all(c.isalnum() or c in '-_' for c in args.run_name):
        raise CheckError('run-name chỉ dùng chữ, số, dấu - và _')
    output = work/'outputs'/args.run_name; output.mkdir(parents=True, exist_ok=True)
    with run_lock(work/'.gpu.lock'):
        snapshot = prepare_input(args.input, work)
        rows, fields, ids, encoding, newline, sha = read_csv(snapshot)
        if args.selection_file:
            if args.all or args.first is not None: raise CheckError('--selection-file chỉ dùng cùng --limit')
            fixed = json.loads(args.selection_file.read_text())
            selected = fixed.get('selected_indices', [])
            if (fixed.get('input_sha256') != sha or fixed.get('rows') != len(rows)
                    or len(selected) != args.limit or len(set(selected)) != len(selected)
                    or any(type(i) is not int or not 0 <= i < len(rows) for i in selected)):
                raise CheckError('Selection manifest khác input hoặc sai danh sách mẫu')
            if any(rows[i]['approve'].strip() for i in selected):
                raise CheckError('Record được chọn đã có nhãn; không ghi đè')
        else:
            selected = ([i for i,r in enumerate(rows) if not r['approve'].strip()]
                        if args.all else ([i for i in range(min(args.first,len(rows))) if not rows[i]['approve'].strip()]
                        if args.first is not None else select_sample(rows, args.limit, args.seed)))
        if args.overrides:
            overrides = json.loads(args.overrides.read_text())
        elif (output/'name_overrides.json').exists():
            overrides = json.loads((output/'name_overrides.json').read_text())
        else: overrides = {}
        old = json.loads((output/'manifest.json').read_text()) if (output/'manifest.json').exists() else None
        base = {'runner': RUN_VERSION, 'code_sha256': code_hash(), 'input_sha256': sha,
                'input_name': snapshot.name, 'rows': len(rows), 'selected_indices': selected,
                'first': args.first,
                'selection_sha256': digest(args.selection_file.read_bytes()) if args.selection_file else None,
                'overrides_sha256': digest(encoded(overrides)), 'url_first': args.url_first,
                'max_pixels': args.max_pixels, 'max_input_tokens': args.max_input_tokens,
                'max_new_tokens': args.max_new_tokens, 'model': args.model,
                'workers': args.workers, 'batch_size': args.batch_size,
                'batch_wait_ms': args.batch_wait_ms, 'batch_token_budget': args.batch_token_budget}
        if args.prepare_only:
            atomic_json(output/'selection.json', {'count': len(selected), 'indices': selected,
                                                 'input_sha256': sha, 'mode': 'all' if args.all else ('first' if args.first is not None else 'sample')})
            print(f'Prepared {len(selected)} / {len(rows)} rows; no GPU/model/network used.'); return 0
        if old:
            if not args.resume: raise CheckError('Run đã tồn tại; dùng --resume')
            if any(old.get(k) != v for k,v in base.items()):
                raise CheckError('Input/code/model/cấu hình thay đổi; không thể resume')
            if args.revision != 'main' and args.revision != old['resolved_revision']:
                raise CheckError('Model revision khác checkpoint')
            revision = old['resolved_revision']
        else:
            if args.resume: raise CheckError('Không có checkpoint để resume')
            revision = args.revision
        journal_path = output/'results.jsonl'
        results = load_results(journal_path, set(selected), ids)
        pending = [i for i in selected if i not in results]
        model = None
        fetcher = None
        processing_started = None
        sessions = list((json.loads((output/'summary.json').read_text()).get('sessions', [])
                         if (output/'summary.json').exists() else []))
        started = time.monotonic(); stop = {'requested': False}; fatal = None
        def request_stop(signum, frame):
            stop['requested'] = True
            print('Đã nhận tín hiệu dừng; sẽ lưu checkpoint sau dòng đang xử lý.', flush=True)
        previous = {s: signal.signal(s, request_stop) for s in (signal.SIGINT, signal.SIGTERM)}
        def save():
            export_csv(output/'reviewed.csv', rows, fields, results, encoding, newline)
            elapsed = time.monotonic()-started
            stats = model.report() if model else {'paid_api_calls': 0}
            session = {'started_utc': session_started, 'elapsed_seconds': round(elapsed, 2),
                       'processed_this_session': len(results)-initial_count,
                       'processing_seconds': round(time.monotonic()-processing_started, 2) if processing_started else 0,
                       'rows_per_hour_excluding_load': round((len(results)-initial_count)*3600 /
                           max(time.monotonic()-processing_started, .001), 2) if processing_started else 0,
                       **(fetcher.report() if fetcher else {}), **stats}
            atomic_json(output/'summary.json', {'total_rows': len(rows), 'selected': len(selected),
                'completed': len(results), 'remaining': len(selected)-len(results),
                'counts': dict(Counter(v['approve'] or 'blank' for v in results.values())),
                'reasons': dict(Counter(v['reason'] for v in results.values())),
                'complete': len(results)==len(selected), 'stop_reason': fatal or ('requested' if stop['requested'] else None),
                'sessions': sessions+[session], 'paid_api_calls': 0})
        initial_count = len(results)
        session_started = datetime.now(timezone.utc).isoformat()
        try:
            if pending:
                model = client_factory(work/'cache/gpu', model_id=args.model, revision=revision,
                    max_pixels=args.max_pixels, max_input_tokens=args.max_input_tokens,
                    max_new_tokens=args.max_new_tokens, batch_size=args.batch_size,
                    batch_wait_ms=args.batch_wait_ms, batch_token_budget=args.batch_token_budget)
                if old and model.identity['revision'] != old['resolved_revision']:
                    raise CheckError('Loaded model revision differs from checkpoint')
                atomic_json(output/'manifest.json', {**base, 'resolved_revision': model.identity['revision'],
                                                     'backend_identity': model.identity})
                atomic_json(output/'name_overrides.json', overrides)
                fetcher = TimedFetcher(fetcher_factory(work/'cache/http'))
                pipeline = Pipeline(model, fetcher, overrides)
                processing_started = time.monotonic()
                print(f'GPU ready | record workers={args.workers} | max batch={args.batch_size} | '
                      f'url_first={args.url_first} | throughput excludes model load', flush=True)
                def process(i):
                    r = rows[i]
                    if args.url_first:
                        profile = profile_name(r['entity_name'], overrides.get(r['entity_id']))
                        for field in ('image_url', 'page_url'):
                            hit = exact_match(profile, r[field])
                            if hit:
                                return {'row_id': ids[i], 'row_index': i, 'entity_name': r['entity_name'],
                                        'approve': 'yes', 'reason': field.upper()+'_NAME_MATCH',
                                        'checks': {field:hit}, 'errors': []}
                    return pipeline.process(r, ids[i], i)
                def stopped():
                    if time.monotonic()-started >= args.max_hours*3600:
                        stop['requested'] = True
                    return stop['requested'] or fatal is not None
                consecutive_internal = 0
                iterator = concurrent_rows(pending, process, args.workers, stopped)
                with journal_path.open('a', encoding='utf-8') as journal:
                    for i, future in iterator:
                        r = rows[i]
                        try:
                            value = future.result()
                            consecutive_internal = 0
                        except FatalGPUError as error:
                            fatal = str(error); break  # current row remains pending
                        except Exception as error:
                            # Stop early on systemic bugs instead of labelling entire dataset blank.
                            consecutive_internal += 1
                            if consecutive_internal >= 3:
                                fatal = 'REPEATED_INTERNAL_ERROR: '+type(error).__name__; break
                            value = {'row_id': ids[i], 'row_index': i, 'entity_name': r['entity_name'],
                                     'approve': '', 'reason': 'CHECK_INCOMPLETE',
                                     'errors': [{'step':'internal','error':type(error).__name__}]}
                        value = compact_result(value)
                        journal.write(json.dumps(value, ensure_ascii=False)+'\n')
                        journal.flush(); os.fsync(journal.fileno())
                        results[i] = {k:value[k] for k in ('row_id','row_index','approve','reason')}
                        n = len(results)-initial_count
                        if n % 10 == 0 or n == 1:
                            rate = n/max(time.monotonic()-processing_started, .001)*3600
                            print(f'{len(results)}/{len(selected)} | {rate:.1f} rows/hour | '
                                  f'last={value["approve"] or "blank"} {value["reason"]}', flush=True)
                        if n % args.save_every == 0:
                            save(); fetcher.trim(work/'cache/http', args.http_cache_gb*1024**3)
                        if n % args.bundle_every == 0:
                            save(); checkpoint_zip(work, output, snapshot)
                        if shutil.disk_usage(work).free < args.min_free_gb*1024**3:
                            fatal = 'DISK_SPACE_LOW'; break
                    iterator.close()
                trim_http_cache(work/'cache/http', args.http_cache_gb*1024**3)
            elif not old:
                # Empty dataset of pending rows: no GPU download required.
                atomic_json(output/'manifest.json', {**base, 'resolved_revision': revision})
            save(); checkpoint_zip(work, output, snapshot)
        finally:
            if 'iterator' in locals(): iterator.close()
            if model and hasattr(model, 'close'): model.close()
            for s, handler in previous.items(): signal.signal(s, handler)
        print(f'Output: {output}\nResume bundle: {output / "resume_bundle.zip"}', flush=True)
        if fatal: print('STOP: '+fatal); return 2
        return 0


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--work-dir', type=Path, default=Path('/kaggle/working/tool'))
    p.add_argument('--run-name', default='full_gpu')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--all', action='store_true')
    mode.add_argument('--limit', type=int, default=50)
    mode.add_argument('--first', type=int, help='First N physical CSV data rows; preserve existing labels')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--selection-file', type=Path,
                   help='Use fixed sample indices from JSON; validates input SHA and row count')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--model', default=DEFAULT_MODEL)
    p.add_argument('--revision', default='main')
    p.add_argument('--overrides', type=Path)
    p.add_argument('--workers', type=int, default=4, help='Concurrent records; one shared GPU model')
    p.add_argument('--batch-size', type=int, default=2)
    p.add_argument('--batch-wait-ms', type=float, default=40)
    p.add_argument('--batch-token-budget', type=int, default=8192)
    p.add_argument('--max-pixels', type=int, default=602112)
    p.add_argument('--max-input-tokens', type=int, default=4096)
    p.add_argument('--max-new-tokens', type=int, default=512)
    p.add_argument('--url-first', action=argparse.BooleanOptionalAction, default=True)
    p.add_argument('--max-hours', type=float, default=8)
    p.add_argument('--save-every', type=int, default=100)
    p.add_argument('--bundle-every', type=int, default=1000)
    p.add_argument('--http-cache-gb', type=float, default=1)
    p.add_argument('--min-free-gb', type=float, default=1.5)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if min(args.limit, args.save_every, args.bundle_every, args.max_hours, args.http_cache_gb, args.min_free_gb,
           args.workers, args.batch_size, args.batch_token_budget) <= 0 or args.batch_wait_ms < 0:
        raise CheckError('Các giới hạn phải lớn hơn 0')
    return run(args)


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (CheckError, FatalGPUError, OSError) as e:
        print('LỖI: '+str(e)); raise SystemExit(2)
