#!/usr/bin/env python3
"""Bounded fresh diagnostic run: 100 unfinished seeds plus same-image records."""
import json
import argparse
import sys
import threading
import time
from pathlib import Path

from approve_tool import ROOT, read_csv, export_csv, atomic_json, digest
from csv_exclusions import record_key
from grouped_pipeline import image_groups
import run_grouped_shopaikey as shop

OUT = ROOT / 'outputs/shopaikey_probe100_20261117'


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--invalid10', action='store_true', help='10 recent groups with historical API_INVALID_JSON')
    args = parser.parse_args()
    if args.invalid10:
        OUT = ROOT / 'outputs/shopaikey_invalid10_20261117'
    budget = .25 if args.invalid10 else .5
    if (OUT / 'manifest.json').exists():
        raise RuntimeError('Diagnostic already started; do not rerun paid calls accidentally')
    OUT.mkdir(exist_ok=True)
    parent = ROOT / 'outputs/luna_shopaikey_cheap_remaining_all'
    snapshot, fields, _, enc, nl, _ = read_csv(parent / 'input_snapshot.csv')
    finished = {json.loads(line)['row_index'] for line in
                (parent / 'results.jsonl').read_text().splitlines() if line.strip()}
    excluded = set(json.loads((parent / 'export_exclusions.json').read_text())['record_keys'])
    identity = [f for f in fields if f != 'approve']
    available = [i for i, row in enumerate(snapshot) if i not in finished
                 and record_key(row, identity) not in excluded and not row['approve'].strip()]
    seeds = available[:100]
    if args.invalid10:
        available_set = set(available)
        events = [json.loads(l) for l in (parent / 'deferred_groups.jsonl').read_text().splitlines() if l.strip()]
        seeds = []
        urls = set()
        for event in reversed(events):
            if event['error'] != 'API_INVALID_JSON':
                continue
            for i in event['row_indices']:
                if i in available_set and snapshot[i]['image_url'] not in urls:
                    seeds.append(i)
                    urls.add(snapshot[i]['image_url'])
                    break
            if len(seeds) == 10:
                break
        if len(seeds) != 10:
            raise RuntimeError('Not enough eligible historically invalid records')
    expanded, _ = image_groups(snapshot, seeds)
    allowed = set(available)
    selected = [i for i in expanded if i in allowed]
    input_path = OUT / 'diagnostic_input.csv'
    export_csv(input_path, [snapshot[i] for i in selected], fields, {}, enc, nl)
    atomic_json(OUT / 'selection_origin.json', {'parent_run': str(parent),
        'parent_snapshot_sha256': digest((parent / 'input_snapshot.csv').read_bytes()),
        'seed_indices': seeds, 'original_indices': selected,
        'seed_records': len(seeds), 'expanded_records': len(selected),
        'budget_credit': budget, 'workers': 4, 'retries': 0,
        'selection_reason': 'historical API_INVALID_JSON' if args.invalid10 else 'unfinished'})
    diag = OUT / 'diagnostics'
    diag.mkdir(exist_ok=True)
    original_client = shop.ShopClient
    lock = threading.Lock()
    counter = [0]
    save_all_responses = args.invalid10

    class DiagnosticClient(original_client):
        def ask(self, task, instruction, data, output_schema, image=None):
            # Each thread records its own request and response, no key/headers.
            local = getattr(self, '_diagnostic_local', None)
            if local is None:
                with lock:
                    if not hasattr(self, '_diagnostic_local'):
                        self._diagnostic_local = threading.local()
                    local = self._diagnostic_local
            local.task = task
            local.schema = output_schema
            local.input_chars = len(json.dumps(data, ensure_ascii=False)) + len(instruction)
            local.has_image = bool(image)
            return super().ask(task, instruction, data, output_schema, image)

        def __init__(self, *args, **kwargs):
            original_transport = kwargs['transport']
            def capture(payload):
                start = time.monotonic()
                response = original_transport(payload)
                text = ''.join(p.get('text', '') for item in response.get('output', [])
                               for p in item.get('content', []) if p.get('type') == 'output_text')
                schema = payload['text']['format']['schema']
                issues = []
                try:
                    v = json.loads(text)
                    if not isinstance(v, dict):
                        issues.append('not_object')
                    else:
                        missing, extra = set(schema['required']) - set(v), set(v) - set(schema['required'])
                        if missing: issues.append('missing:' + ','.join(sorted(missing)))
                        if extra: issues.append('extra:' + ','.join(sorted(extra)))
                        for k, spec in schema['properties'].items():
                            if k not in v: continue
                            x = v[k]
                            if spec['type'] == 'string' and not isinstance(x, str): issues.append('type:' + k)
                            if spec['type'] == 'integer' and type(x) is not int: issues.append('type:' + k)
                            if spec['type'] == 'array' and (not isinstance(x, list) or not all(isinstance(z, str) for z in x)): issues.append('type:' + k)
                            if 'enum' in spec and x not in spec['enum']: issues.append('enum:' + k)
                except (ValueError, TypeError):
                    issues.append('json_syntax')
                info = {'utc_epoch': time.time(), 'task': payload['text']['format']['name'],
                        'response_id': response.get('id'), 'status': response.get('status'),
                        'usage': response.get('usage'), 'issues': issues,
                        'elapsed_seconds': round(time.monotonic() - start, 2),
                        'request_text_chars': sum(len(m['content']) if isinstance(m['content'], str)
                             else sum(len(p.get('text', '')) for p in m['content']) for m in payload['input']),
                        'has_image': any(p.get('type') == 'input_image' for m in payload['input']
                                         if isinstance(m['content'], list) for p in m['content'])}
                with lock:
                    counter[0] += 1
                    if save_all_responses or issues or response.get('status') != 'completed':
                        info.update(raw_response=response, requested_schema=schema)
                        atomic_json(diag / f'response_{counter[0]:04}.json', info)
                    with (diag / 'requests.jsonl').open('a', encoding='utf-8') as f:
                        f.write(json.dumps({k: v for k, v in info.items() if k not in
                                            ('raw_response', 'requested_schema')}, ensure_ascii=False) + '\n')
                return response
            kwargs['transport'] = capture
            super().__init__(*args, **kwargs)

    shop.ShopClient = DiagnosticClient
    try:
        return shop.main(['--input', str(input_path), '--first', str(len(selected)),
            '--output-dir', str(OUT), '--workers', '4', '--budget-credit', str(budget), '--run'])
    finally:
        shop.ShopClient = original_client


if __name__ == '__main__':
    raise SystemExit(main())
