#!/usr/bin/env python3
"""Replay the audited final 100 records against official OpenAI, isolated from production."""
import csv
import json
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

from approve_tool import ROOT, CheckError, read_csv, atomic_json, encoded, digest, load_env, export_csv
from api_providers import ProviderFatal, ProviderLedger
from api_economy import StopBudget
from compatible_chat import NoRedirect
from run_grouped_shopaikey import ShopClient, SingleAttemptFetcher, normalize_ocr_response
from grouped_user_rules import UserRulesGroupPipeline
from source_subject_guard import SourceSubjectClient

OUT = ROOT / 'outputs/official_vs_shopaikey_latest100_20261118'
PARENT = ROOT / 'outputs/luna_shopaikey_cheap_remaining_all'


def main():
    OUT.mkdir(exist_ok=True)
    if (OUT / 'started.json').exists():
        raise RuntimeError('Run already started; inspect before repeating paid calls')
    # Explicitly take the user's key from tool/.env, never a shell override.
    previous = os.environ.pop('OPENAI_API_KEY', None)
    load_env(ROOT / '.env')
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not key:
        raise RuntimeError('Missing OPENAI_API_KEY in tool/.env')
    rows, fields, ids, enc, nl, sha = read_csv(PARENT / 'input_snapshot.csv')
    journal = [json.loads(l) for l in (PARENT / 'results.jsonl').read_text().splitlines() if l.strip()]
    sample = journal[-100:]
    by_index = {r['row_index']: r for r in journal}
    urls = {rows[r['row_index']]['image_url'] for r in sample}
    groups = {}
    for i, row in enumerate(rows):
        if row['image_url'] in urls:
            groups.setdefault(row['image_url'], []).append(i)
    selected = sorted(i for group in groups.values() for i in group)
    atomic_json(OUT / 'selection.json', {'parent': str(PARENT), 'snapshot_sha': sha,
        'sample_indices': [r['row_index'] for r in sample], 'expanded_indices': selected,
        'sample_records': len(sample), 'image_groups': len(groups), 'expanded_records': len(selected),
        'model': 'gpt-6-luna', 'endpoint': 'https://api.openai.com/v1/responses',
        'policy': 'user-rules-v4 + image-subject-guard-v2; identical prompts and 1800 output cap',
        'workers': 4, 'budget_usd': 0.50, 'cache': 'isolated model cache; shared cached source/image bytes',
        'estimated_rates_from_existing_config': {'input_per_million': .10, 'output_per_million': .50}})
    export_csv(OUT / 'input.csv', [rows[i] for i in selected], fields, {}, enc, nl)
    ledger = ProviderLedger(OUT / 'usage.json', .50, (.10, .50))
    lock = threading.Lock()
    call_counter = [0]

    def transport(payload):
        payload = dict(payload, model='gpt-6-luna', max_output_tokens=1800)
        started = time.monotonic()
        req = Request('https://api.openai.com/v1/responses', data=encoded(payload),
            headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        with lock:
            call_counter[0] += 1
            number = call_counter[0]
        try:
            with build_opener(NoRedirect()).open(req, timeout=90) as response:
                raw = json.load(response)
        except HTTPError as error:
            code = error.code
            try:
                info = json.loads(error.read(65536)).get('error', {})
                safe = {k: info.get(k) for k in ('code', 'type', 'message')}
                # Credential values are never written, even if echoed by a gateway.
                safe = json.loads(json.dumps(safe).replace(key, '[REDACTED]'))
            except (ValueError, TypeError):
                safe = {}
            error.close()
            atomic_json(OUT / f'http_error_{number:03}.json', {'status': code, 'error': safe})
            raise ProviderFatal(f'OFFICIAL_HTTP_{code}') from None
        except (URLError, OSError, TimeoutError):
            raise ProviderFatal('OFFICIAL_NETWORK_ERROR') from None
        atomic_json(OUT / f'response_{number:03}.json', {'task': payload['text']['format']['name'],
            'elapsed_seconds': round(time.monotonic()-started, 3), 'response': raw})
        return normalize_ocr_response(raw, payload)

    client = SourceSubjectClient(ShopClient(key, ledger, OUT / 'model_cache',
        provider='openai-official-comparison', model='gpt-6-luna',
        base_url='https://api.openai.com/v1/responses', transport=transport))
    engine = UserRulesGroupPipeline(client, SingleAttemptFetcher(ROOT / 'cache/http'),
        require_ocr_response=True, one_yes_per_image=False)
    results = {}
    errors = []
    atomic_json(OUT / 'started.json', {'epoch': time.time(), 'paid_calls_authorized': True})

    def process(group):
        items = [(i, rows[i], ids[i]) for i in group]
        answers = engine.process_group(items)
        failures = [e for r in answers for e in r.get('errors', [])
                    if e.get('error') != 'TARGET_IMAGE_CONTEXT_NOT_FOUND']
        if failures:
            raise CheckError(failures[0]['error'])
        return answers

    def collect(group, answers):
        for r in answers:
            results[r['row_index']] = r
        with (OUT / 'results.jsonl').open('a') as f:
            for r in answers:
                f.write(json.dumps(r, ensure_ascii=False)+'\n')
        print(f'{len(results)}/{len(selected)} records | group {len(group)} | estimated<=${ledger.total():.4f}', flush=True)

    work = list(groups.values())
    # Validate real model/key access with the first actual group before parallel calls.
    try:
        collect(work[0], process(work[0]))
    except (ProviderFatal, CheckError, StopBudget) as error:
        atomic_json(OUT / 'stopped.json', {'reason': str(error), 'api_attempts': call_counter[0]})
        print('STOP:', str(error), flush=True)
        return 2
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(process, g): g for g in work[1:]}
        for future in as_completed(futures):
            group = futures[future]
            try:
                collect(group, future.result())
            except (ProviderFatal, CheckError, StopBudget) as error:
                errors.append({'indices': group, 'error': str(error)})
                atomic_json(OUT / 'errors.json', errors)
                print('ERROR:', str(error), flush=True)
    comparison = []
    for old in sample:
        i = old['row_index']; new = results.get(i, {})
        comparison.append({'snapshot_data_row': i+1, 'entity_name': old['entity_name'],
            'shop_label': old['approve'], 'official_label': new.get('approve', ''),
            'shop_reason': old['reason'], 'official_reason': new.get('reason', ''),
            'same_label': old['approve']==new.get('approve'),
            'official_errors': json.dumps(new.get('errors', []), ensure_ascii=False)})
    with (OUT / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(comparison[0]));w.writeheader();w.writerows(comparison)
    atomic_json(OUT / 'summary.json', {'sample_records': len(sample), 'expanded_records':len(selected),
        'completed': len(results), 'shop_counts': dict(Counter(r['approve'] for r in sample)),
        'official_sample_counts': dict(Counter(r['official_label'] or 'blank' for r in comparison)),
        'label_differences': sum(not r['same_label'] for r in comparison),
        'group_errors': errors, 'ledger': ledger.report()})
    print('OUTPUT:', OUT, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
