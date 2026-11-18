#!/usr/bin/env python3
"""Luna on ShopAIKey Cheap API. Preview by default; separate credentials/cache."""
import argparse
import builtins
import json
import math
import os
import threading
import tempfile
import time
from pathlib import Path
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin

from approve_tool import ROOT, CheckError, load_env, atomic_json, digest, within
from approve_tool import HTTP_CACHE_VERSION, encoded, public_url, NoRedirect
from api_providers import ProviderFatal, ProviderLedger
from shopaikey_responses import responses_request
from api_economy import StopBudget
from grouped_user_rules import UserRulesGroupPipeline
import run_grouped_luna_standard as runner

RATES = (.24, .90)
CACHE_READ = .024
CACHE_WRITE = .30
VND_PER_CREDIT = 3250
ENDPOINT = 'https://api.shopaikey.com/v1'
LOGGING_COMPATIBLE_RUNNERS = {'470ca22c89bf3bdfe8e8957a92666b4c07f34e2a649c6ca8e3893d96a7e3251a'}
LOGGING_COMPATIBLE_RUNNERS.add('d2f63eb95672c97dcf88da04d8683368bdd687babe873ff20429a19969747b4e')
LOGGING_COMPATIBLE_RUNNERS.add('b27cc4fd0b95992691beba3e2d4919412b232af7e5a7e80e2d9e124af1d0857c')
LOGGING_COMPATIBLE_RUNNERS.add('0c1b38335f7971b8d2e46df5845091567e179f35679f50c59039857c30b9ea12')
LOGGING_COMPATIBLE_RUNNERS.add('8af9595dca31261017af3825c5fe2b299ce42ef3298c10dcec72688d358a0039')
LOGGING_COMPATIBLE_RUNNERS.add('c3be0afff7532d5a799eb623706b0eca890aecc3f1b0107b8f15aee9878552c3')
PROGRESS = {'completed': 0, 'total': 0, 'skipped': 0, 'ledger': None}
PROGRESS_LOCK = threading.Lock()


def normalize_ocr_response(response, payload):
    """Ignore a gateway's unsolicited explanation, only after validating OCR fields."""
    if payload['text']['format']['name'] != 'observe' or response.get('status') != 'completed':
        return response
    parts = [p for item in response.get('output', []) for p in item.get('content', [])
             if p.get('type') == 'output_text']
    try:
        value = json.loads(''.join(p['text'] for p in parts))
    except (ValueError, TypeError, KeyError):
        return response
    if (not isinstance(value, dict) or set(value) != {'status', 'texts', 'explanation'}
            or value['status'] not in ('readable', 'no_text', 'unreadable')
            or not isinstance(value['texts'], list)
            or not all(isinstance(x, str) for x in value['texts'])
            or not isinstance(value['explanation'], str)):
        return response
    # No semantic inference, guessed characters or labels; preserve literal OCR.
    response = dict(response, output=[{'type': 'message', 'content': [{'type': 'output_text',
        'text': json.dumps({'status': value['status'], 'texts': value['texts']}, ensure_ascii=False)}]}])
    return response


def progress_print(*args, **kwargs):
    # The group wrapper already emits a short, accurate failure reason.
    # Keep scheduler progress/output unchanged and suppress its duplicate warning.
    if args and str(args[0]).startswith('NETWORK_ERROR:'):
        return
    with PROGRESS_LOCK:
        msg = str(args[0]) if args else ''
        if msg.startswith('[skip] group '):
            PROGRESS['skipped'] += 1
            group, _, reason = msg.removeprefix('[skip] group ').partition(' | ')
            ledger = PROGRESS['ledger']
            cost = ledger.total() if ledger else 0
            msg = (f"{PROGRESS['completed']}/{PROGRESS['total']} records | group {group} | "
                   f"cost<=${cost:.4f} | skip={PROGRESS['skipped']} {reason}")
            args = (msg, *args[1:])
        elif ' records | group ' in msg and '/' in msg:
            head = msg.split(' records', 1)[0]
            done, _, total = head.partition('/')
            if done.isdigit() and total.isdigit():
                PROGRESS.update(completed=int(done), total=int(total))
        builtins.print(*args, **kwargs)


def defer_previous_last(groups, log_path):
    """Stable partition; selected records and membership are never changed."""
    failed = set()
    if log_path.exists():
        for line in log_path.read_text().splitlines():
            try:
                failed.update(json.loads(line)['row_indices'])
            except (ValueError, KeyError, TypeError):
                continue
    return sorted(groups, key=lambda group: any(i in failed for i in group))


class ContinuingPipeline(UserRulesGroupPipeline):
    """One attempt per group; failures stay pending without a label."""
    output_dir = None
    log_lock = threading.Lock()
    records_deferred = True

    def check_group(self, items):
        return super().process_group(items)

    def process_group(self, items):
        last_error = 'UNKNOWN_CHECK_ERROR'
        for attempt in range(1):
            try:
                answers = self.check_group(items)
                failures = [e for r in answers for e in r.get('errors', [])
                            if e.get('error') != 'TARGET_IMAGE_CONTEXT_NOT_FOUND']
                if not failures:
                    return answers
                last_error = str(failures[0].get('error', 'UNKNOWN_CHECK_ERROR'))
            except StopBudget:
                raise
            except Exception as error:
                last_error = str(error) if isinstance(error, (CheckError, ProviderFatal)) else type(error).__name__
                # Authentication/quota are global, not a bad individual group.
                if isinstance(error, ProviderFatal) and any(
                        code in last_error for code in ('CHAT_HTTP_401', 'CHAT_HTTP_402', 'CHAT_HTTP_403')):
                    raise
        event = {'row_indices': [i for i, _, _ in items],
                 'row_ids': [rid for _, _, rid in items], 'error': last_error,
                 'attempts': 1, 'timestamp': time.time(), 'action': 'deferred_without_label'}
        with self.log_lock:
            with (self.output_dir / 'deferred_groups.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
                f.flush()
                os.fsync(f.fileno())
        code = last_error.split(':', 1)[0].splitlines()[0][:80]
        progress_print(f'[skip] group {len(items)} | {code}', flush=True)
        # Reuse the scheduler's existing deferred-group path. Detailed cause is
        # saved separately; no failed result enters results.jsonl or the CSV.
        raise ProviderFatal('API_NETWORK_ERROR')


class ShopClient(runner.StandardClient):
    """No task retries: pipeline handles failures without committing NO."""


class SingleAttemptFetcher(runner.StandardFetcher):
    """Shared HTTP cache and redirect handling, with no network/status retries."""
    def fetch(self, url, kind):
        key = digest(encoded([HTTP_CACHE_VERSION, url, kind]))
        data_path, meta_path = self.cache / (key + '.bin'), self.cache / (key + '.json')
        if data_path.exists() and meta_path.exists():
            return data_path.read_bytes(), json.loads(meta_path.read_text())
        current = url
        for _ in range(6):
            public_url(current)
            req = Request(current, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; LocalImageReview/1.0)',
                'Accept': '*/*', 'Accept-Encoding': 'identity'})
            try:
                response = build_opener(NoRedirect).open(req, timeout=20)
                with response:
                    limit = 12_000_000 if kind == 'image' else 3_000_000
                    data = response.read(limit + 1)
                    if len(data) > limit:
                        raise CheckError('FETCH_TOO_LARGE')
                    meta = {'url': current, 'content_type': response.headers.get_content_type(),
                            'charset': response.headers.get_content_charset() or 'utf-8'}
            except HTTPError as error:
                location = error.headers.get('Location')
                code = error.code
                error.close()
                if code in (301, 302, 303, 307, 308) and location:
                    current = urljoin(current, location)
                    continue
                raise CheckError(f'HTTP_{code}') from None
            except UnicodeEncodeError:
                raise CheckError('FETCH_URL_ENCODING_ERROR') from None
            except (URLError, OSError, TimeoutError):
                raise CheckError('FETCH_NETWORK_ERROR') from None
            with tempfile.NamedTemporaryFile('wb', dir=self.cache, delete=False) as f:
                f.write(data)
                tmp = f.name
            os.replace(tmp, data_path)
            atomic_json(meta_path, meta)
            return data, meta
        raise CheckError('TOO_MANY_REDIRECTS')


class ShopLedger(ProviderLedger):
    def finish(self, idx, usage):
        details = usage.get('input_tokens_details') or {}
        inp, out = usage['input_tokens'], usage['output_tokens']
        cached = details.get('cached_tokens', 0)
        written = details.get('cache_write_tokens', 0)
        if any(type(v) is not int or v < 0 for v in (cached, written)) or cached + written > inp:
            raise ProviderFatal('SHOPAIKEY_INVALID_CACHE_USAGE')
        cost = ((inp - cached - written) * RATES[0] + cached * CACHE_READ
                + written * CACHE_WRITE + out * RATES[1]) / 1e6
        with self.lock:
            self.data['calls'][idx] = {'state': 'reported',
                'charged_or_reserved_usd': cost, 'usage': usage}
            atomic_json(self.path, self.data)


def transport(key, payload):
    # ModelClient's neutral internal payload still carries its historical model ID.
    payload = dict(payload, model='gpt-6-luna', max_output_tokens=1800)
    try:
        return normalize_ocr_response(responses_request(key, payload), payload)
    except ProviderFatal as error:
        if str(error).startswith('CHAT_NETWORK_ERROR'):
            raise ProviderFatal('API_NETWORK_ERROR') from None
        raise


def main(argv=None):
    load_env(ROOT / '.env')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, default=ROOT.parent / 'general_10m_part_02.csv')
    p.add_argument('--output-dir', type=Path)
    p.add_argument('--pilot', action='store_true')
    p.add_argument('--image-quality', action='store_true', help='Kiểm ảnh + OCR trước URL; dùng output mới')
    p.add_argument('--policy', choices=('user-rules-v5','user-rules-v4'), default='user-rules-v5')
    p.add_argument('--first', type=int, default=3000)
    p.add_argument('--start-row', type=int, default=1)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--budget-credit', type=float, default=1,
                   help='Shop credit; $1 credit = 3.250đ, không phải USD thật')
    p.add_argument('--run', action='store_true')
    p.add_argument('--resume', action='store_true')
    a = p.parse_args(argv)
    if a.output_dir is None:
        a.output_dir = ROOT / 'outputs' / ('luna_shopaikey_quality_pilot50' if a.image_quality
                                         else 'luna_shopaikey_cheap_pilot50')
        if a.policy=='user-rules-v5':
            a.output_dir=a.output_dir.with_name(a.output_dir.name+'_v5')
    if (not math.isfinite(a.budget_credit) or
            min(a.first, a.start_row, a.workers, a.budget_credit) <= 0 or a.workers > 16):
        raise CheckError('Số dòng/workers/budget không hợp lệ')
    key = os.environ.get('SHOPAIKEY_API_KEY', '').strip()
    if a.run and not key:
        raise CheckError('Điền SHOPAIKEY_API_KEY trong tool/.env')
    output = within(a.output_dir, ROOT / 'outputs')
    output.mkdir(parents=True, exist_ok=True)
    settings = {'provider': 'shopaikey', 'expected_group': 'cheap', 'model': 'gpt-6-luna',
        'decision_policy':a.policy,
        'endpoint': ENDPOINT, 'rates_credit_per_million': list(RATES),
        'api': 'responses',
        'responses_adapter_sha256': digest((ROOT / 'shopaikey_responses.py').read_bytes()),
        'cache_read_credit_per_million': CACHE_READ, 'cache_write_credit_per_million': CACHE_WRITE,
        'vnd_per_credit': VND_PER_CREDIT, 'source_guard': True,
        'runner_sha256': digest(Path(__file__).read_bytes()),
        'chat_adapter_sha256': digest((ROOT / 'compatible_chat.py').read_bytes()),
        'source_guard_sha256': digest((ROOT / 'source_subject_guard.py').read_bytes())}
    if a.image_quality:
        from image_quality import RULE_PATH, VERSION
        settings.update(image_quality=VERSION, image_quality_rules_sha256=digest(RULE_PATH.read_bytes()),
                        image_quality_code_sha256=digest((ROOT / 'image_quality.py').read_bytes()))
    marker = output / 'shopaikey_settings.json'
    if marker.exists():
        previous = json.loads(marker.read_text())
        if previous != settings:
            if previous.get('image_quality') != settings.get('image_quality'):
                raise CheckError('Policy kiểm ảnh thay đổi; dùng output mới để không bỏ sót ảnh đã duyệt bằng URL')
            ignored = {'runner_sha256'}
            if 'api' not in previous:
                ignored.update({'api', 'responses_adapter_sha256'})
            compatible = (a.resume and previous.get('runner_sha256') in LOGGING_COMPATIBLE_RUNNERS
                          and {k: v for k, v in previous.items() if k not in ignored} ==
                              {k: v for k, v in settings.items() if k not in ignored})
            if not compatible:
                raise CheckError('Cấu hình đổi; dùng output mới')
            atomic_json(output / 'logging_upgrade.json', {'before': previous, 'after': settings,
                'reason': 'Audited upgrade: native Responses endpoint (Chat route injects/reports ~18k extra input), no retries at any layer, failed groups last. Existing journal preserved; pending requests use separate Responses cache.'})
    if (output / 'manifest.json').exists() and not marker.exists():
        raise CheckError('Output thuộc runner khác')
    atomic_json(marker, settings)

    def client_factory(unused_key, ledger, unused_cache, **kwargs):
        PROGRESS['ledger'] = ledger
        client = ShopClient(key, ledger, output / 'model_cache',
            provider='shopaikey', model='gpt-6-luna', base_url=ENDPOINT + '/responses',
            transport=lambda payload: transport(key, payload))
        if a.image_quality:
            from image_quality import ImageQualityObserver
            client = ImageQualityObserver(client)
        from source_subject_guard import SourceSubjectClient
        return SourceSubjectClient(client)

    # Scope scheduler overrides to this process; existing Luna/DeepSeek code and
    # environment file remain untouched. Provider tag isolates all model caches.
    old_price, old_load, old_ledger = runner.price_for, runner.load_env, runner.ProviderLedger
    old_export = runner.export_csv
    exclusion_file = output / 'export_exclusions.json'
    if exclusion_file.exists():
        from csv_exclusions import filtered_export
        runner.export_csv = filtered_export(old_export, json.loads(exclusion_file.read_text()))
    old_image_groups = runner.image_groups
    journal_path = output / 'results.jsonl'
    PROGRESS.update(completed=sum(bool(l.strip()) for l in journal_path.read_text().splitlines())
                    if journal_path.exists() else 0, total=0, skipped=0, ledger=None)
    def ordered_image_groups(rows, seed):
        selected, groups = old_image_groups(rows, seed)
        PROGRESS['total'] = len(selected)
        return selected, defer_previous_last(groups, output / 'deferred_groups.jsonl')
    runner.image_groups = ordered_image_groups
    old_print = runner.__dict__.get('print')
    runner.print = progress_print
    import grouped_user_rules
    old_pipeline = grouped_user_rules.UserRulesGroupPipeline
    pipeline_base = ContinuingPipeline
    if a.image_quality:
        from image_quality import ImageQualityGate
        pipeline_base = type('QualityPipeline', (ImageQualityGate, ContinuingPipeline), {})
    class RunPipeline(pipeline_base):
        output_dir = output
    grouped_user_rules.UserRulesGroupPipeline = RunPipeline
    old_key = os.environ.get('OPENAI_API_KEY')
    def credentials(path):
        os.environ['OPENAI_API_KEY'] = key
    runner.price_for = lambda provider, model: RATES
    runner.load_env = credentials
    runner.ProviderLedger = ShopLedger
    args = argparse.Namespace(input=ROOT / 'input/general_10m_part_02_copy.csv' if a.pilot else a.input,
        output_dir=output, baseline_dir=ROOT / 'outputs/luna_v2_2_pilot50' if a.pilot else None,
        unlabeled_only=not a.pilot, group_yes='multiple', policy=a.policy,
        execution='standard', model='gpt-6-luna', start_row=a.start_row, first=50 if a.pilot else a.first,
        workers=a.workers, budget_usd=a.budget_credit, save_every=10, run=a.run, resume=a.resume)
    print('ShopAIKey Cheap: cost hiển thị USD CREDIT (1 credit = 3.250đ). '
          'Nhóm thực tế do key quyết định; code không tự đổi nhóm.', flush=True)
    try:
        return runner.run(args, client_factory=client_factory, fetcher_factory=SingleAttemptFetcher)
    finally:
        runner.export_csv = old_export
        runner.image_groups = old_image_groups
        if old_print is None:
            runner.__dict__.pop('print', None)
        else:
            runner.print = old_print
        grouped_user_rules.UserRulesGroupPipeline = old_pipeline
        runner.price_for, runner.load_env, runner.ProviderLedger = old_price, old_load, old_ledger
        if old_key is None:
            os.environ.pop('OPENAI_API_KEY', None)
        else:
            os.environ['OPENAI_API_KEY'] = old_key


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (CheckError, OSError, ProviderFatal) as error:
        print('LỖI:', error)
        raise SystemExit(2)
