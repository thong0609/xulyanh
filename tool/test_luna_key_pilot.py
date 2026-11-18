#!/usr/bin/env python3
"""Re-run the original Luna pilot with an isolated model cache; offline by default."""
import argparse
import json
from pathlib import Path

from approve_tool import ROOT, CheckError, atomic_json, within, digest
from api_providers import ProviderFatal
from run_grouped_luna_standard import run, StandardClient


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, default=ROOT/'outputs/luna_grouped_standard_v4_pilot50_newkey')
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--budget-usd', type=float, default=0.50)
    p.add_argument('--run', action='store_true')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--base-url', help='HTTPS Base URL của bên trung gian, ví dụ https://modelapi.vn/v1')
    p.add_argument('--source-guard', action='store_true', help='Thử phân biệt chủ thể ảnh với mô tả chung')
    p.add_argument('--reuse-ocr-from', type=Path, help='Chỉ tái sử dụng cache OCR của pilot cũ')
    p.add_argument('--input', type=Path, default=ROOT/'input/general_10m_part_02_copy.csv')
    p.add_argument('--first', type=int, help='Lấy N dòng đầu thay vì mẫu pilot cũ, vẫn mở rộng nhóm ảnh')
    p.add_argument('--unlabeled-only', action='store_true')
    a = p.parse_args()
    if not 1 <= a.workers <= 16 or a.budget_usd <= 0:
        raise CheckError('Invalid workers or budget')
    if a.first is not None and a.first <= 0:
        raise CheckError('--first phải dương')
    if a.unlabeled_only and a.first is None:
        raise CheckError('--unlabeled-only cần --first')
    output = within(a.output_dir, ROOT/'outputs')
    cache = output/'model_cache'
    settings = {'pipeline': 'user-rules-v4', 'model': 'gpt-6-luna',
                'seed_baseline': 'luna_v2_2_pilot50' if a.first is None else None,
                'model_cache': str(cache), 'http_cache': 'shared; no model answers reused from old runs'}
    if a.first is not None:
        settings.update(input=str(a.input.resolve()),first=a.first,unlabeled_only=a.unlabeled_only)
    endpoint = None
    if a.base_url:
        from compatible_chat import base_url
        endpoint = base_url(a.base_url)
        settings.update(base_url=endpoint, api='chat_completions',
                        adapter_sha256=digest((ROOT/'compatible_chat.py').read_bytes()))
    if a.source_guard:
        settings.update(source_guard=digest((ROOT/'source_subject_guard.py').read_bytes()))
    if a.reuse_ocr_from:
        settings['reuse_ocr_from'] = str(a.reuse_ocr_from.resolve())
    marker = output/'key_pilot_settings.json'
    if (output/'manifest.json').exists() and not marker.exists():
        raise CheckError('Output belongs to another runner; choose a new output directory')
    if marker.exists() and json.loads(marker.read_text()) != settings:
        raise CheckError('Pilot cache settings changed; use a new output directory')
    atomic_json(marker, settings)
    if a.reuse_ocr_from:
        origin = within(a.reuse_ocr_from, ROOT/'outputs')/'model_cache'
        if not origin.exists():
            raise CheckError('Không tìm thấy model_cache để tái sử dụng OCR')
        count = 0
        for path in origin.rglob('*.json'):
            value = json.loads(path.read_text())
            if (set(value) == {'status', 'texts'} and value['status'] in ('readable', 'no_text', 'unreadable')
                    and isinstance(value['texts'], list) and all(isinstance(x, str) for x in value['texts'])):
                target = cache/path.relative_to(origin)
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open('xb') as f:
                        f.write(path.read_bytes())
                    count += 1
        print('Đã tái sử dụng', count, 'cache OCR; không tái sử dụng kết quả kiểm nguồn.')

    def fresh_client(key, ledger, unused_cache, **kwargs):
        if endpoint:
            from compatible_chat import chat_request
            def transport(payload):
                payload = dict(payload, model=kwargs['model'], max_output_tokens=900)
                return chat_request(endpoint, key, payload)
            kwargs.update(base_url=endpoint, transport=transport)
        client = StandardClient(key, ledger, cache, **kwargs)
        if a.source_guard:
            from source_subject_guard import SourceSubjectClient
            return SourceSubjectClient(client)
        return client

    args = argparse.Namespace(input=a.input,
        output_dir=output, baseline_dir=ROOT/'outputs/luna_v2_2_pilot50' if a.first is None else None,
        unlabeled_only=a.unlabeled_only, group_yes='multiple', policy='user-rules-v4',
        execution='standard', model='gpt-6-luna', start_row=1, first=a.first if a.first is not None else 50,
        workers=a.workers, budget_usd=a.budget_usd, save_every=10,
        run=a.run, resume=a.resume)
    return run(args, client_factory=fresh_client)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (CheckError, OSError, ProviderFatal) as e:
        print('LỖI:', e)
        raise SystemExit(2)
