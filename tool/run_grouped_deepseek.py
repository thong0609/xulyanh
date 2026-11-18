#!/usr/bin/env python3
"""Grouped user rules v4 using GenzShop DeepSeek. Offline preview by default."""
import argparse
import json
import os
from pathlib import Path

from approve_tool import ROOT, CheckError, load_env, atomic_json, digest, within
from api_providers import ProviderFatal, ProviderLedger
from genz_deepseek import messages_request
import run_grouped_luna_standard as runner


class CreditLedger(ProviderLedger):
    def finish(self, idx, usage):
        details = usage.get('input_tokens_details') or {}
        # Shop publishes cache read at $0.006/M for Flash-1017. Treat
        # undocumented cache writes as ordinary input, conservatively.
        cached = min(usage['input_tokens'], details.get('cached_tokens', 0))
        with self.lock:
            cost = ((usage['input_tokens'] - cached) * self.rates[0]
                    + cached * .006 + usage['output_tokens'] * self.rates[1]) / 1e6
            self.data['calls'][idx] = {'state': 'reported',
                'charged_or_reserved_usd': cost, 'usage': usage}
            atomic_json(self.path, self.data)


def main(argv=None):
    load_env(ROOT / '.env')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, default=ROOT.parent / 'general_10m_part_02.csv')
    p.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/deepseek_genz_pilot50')
    p.add_argument('--pilot', action='store_true', help='Đúng pilot 50 cũ, mở rộng 85 record')
    p.add_argument('--first', type=int, default=3000)
    p.add_argument('--start-row', type=int, default=1)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--budget-credit', type=float, default=1, help='USD credit shop, $1 credit = 1.500đ')
    p.add_argument('--base-url', default=os.environ.get('DEEPSEEK_BASE_URL', 'https://1gw.gwai.cloud/v1'))
    p.add_argument('--model', default=os.environ.get('DEEPSEEK_MODEL', 'deepseek-v4.1-flash-1017'),
                   choices=['deepseek-v4.1-flash-1017'])
    p.add_argument('--run', action='store_true')
    p.add_argument('--resume', action='store_true')
    a = p.parse_args(argv)
    if min(a.first, a.start_row, a.workers, a.budget_credit) <= 0 or a.workers > 16:
        raise CheckError('Số dòng, workers hoặc budget không hợp lệ')
    from compatible_chat import base_url
    endpoint = base_url(a.base_url)
    output = within(a.output_dir, ROOT / 'outputs')
    output.mkdir(parents=True, exist_ok=True)
    settings = {'provider': 'genz-deepseek', 'model': a.model, 'base_url': endpoint,
                'api': 'anthropic_messages', 'rates_credit_per_million': [.30, 1.20],
                'cache_read_credit_per_million': .006, 'vnd_per_credit': 1500,
                'source_guard': True, 'adapter_sha256': digest((ROOT / 'genz_deepseek.py').read_bytes()),
                'runner_sha256': digest(Path(__file__).read_bytes())}
    marker = output / 'deepseek_settings.json'
    if marker.exists() and json.loads(marker.read_text()) != settings:
        raise CheckError('Cấu hình DeepSeek thay đổi; dùng output mới')
    if (output / 'manifest.json').exists() and not marker.exists():
        raise CheckError('Output thuộc runner khác; dùng output mới')
    if a.run and not os.environ.get('DEEPSEEK_API_KEY', '').strip():
        raise CheckError('Điền DEEPSEEK_API_KEY trong tool/.env')
    atomic_json(marker, settings)

    def client_factory(unused_key, ledger, unused_cache, **kwargs):
        key = os.environ['DEEPSEEK_API_KEY'].strip()
        transport = lambda payload: messages_request(endpoint, key, payload, a.model)
        client = runner.StandardClient(key, ledger, output / 'model_cache',
            provider='genz-deepseek', model=a.model, base_url=endpoint, transport=transport)
        from source_subject_guard import SourceSubjectClient
        return SourceSubjectClient(client)

    # Reuse the existing scheduler without altering the OpenAI runner on disk.
    # Its credential/rate hooks are scoped to this dedicated process and restored.
    old_price, old_load, old_ledger = runner.price_for, runner.load_env, runner.ProviderLedger
    old_key = os.environ.get('OPENAI_API_KEY')
    def credentials(path):
        load_env(path)
        os.environ['OPENAI_API_KEY'] = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    runner.price_for = lambda provider, model: (.30, 1.20)
    runner.load_env = credentials
    runner.ProviderLedger = CreditLedger
    args = argparse.Namespace(input=ROOT / 'input/general_10m_part_02_copy.csv' if a.pilot else a.input,
        output_dir=output, baseline_dir=ROOT / 'outputs/luna_v2_2_pilot50' if a.pilot else None,
        unlabeled_only=not a.pilot, group_yes='multiple', policy='user-rules-v4',
        execution='standard', model=a.model, start_row=a.start_row, first=50 if a.pilot else a.first,
        workers=a.workers, budget_usd=a.budget_credit, save_every=10, run=a.run, resume=a.resume)
    print('Chi phí hiển thị bằng USD CREDIT shop; $1 credit = 1.500đ, không phải USD OpenAI.', flush=True)
    try:
        return runner.run(args, client_factory=client_factory)
    finally:
        runner.price_for, runner.load_env, runner.ProviderLedger = old_price, old_load, old_ledger
        if old_key is None:
            os.environ.pop('OPENAI_API_KEY', None)
        else:
            os.environ['OPENAI_API_KEY'] = old_key


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (CheckError, OSError, ProviderFatal) as e:
        print('LỖI:', e)
        raise SystemExit(2)
