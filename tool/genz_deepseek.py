"""GenzShop's documented Anthropic Messages endpoint; no paid calls on import."""
import json
import random
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

from approve_tool import encoded
from api_providers import ProviderFatal
from compatible_chat import base_url, NoRedirect

_cooldown_lock = threading.Lock()
_retry_until = 0.0


def retry_delay(headers, attempt):
    value = headers.get('Retry-After', '')
    try:
        delay = float(value)
    except (TypeError, ValueError):
        try:
            delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            delay = 5 * 2 ** attempt
    return max(1, delay) + random.uniform(0, 2)


def wait_for_gateway():
    global _retry_until
    while True:
        with _cooldown_lock:
            delay = _retry_until - time.monotonic()
            if delay <= 0:
                # Space retries from concurrent workers after a shared cooldown.
                _retry_until = time.monotonic() + .25
                return
        time.sleep(min(delay, 30))


def messages_payload(payload, model):
    system = []
    messages = []
    for message in payload['input']:
        if message['role'] in ('system', 'developer'):
            system.append(message['content'])
            continue
        content = message['content']
        if isinstance(content, list):
            parts = []
            for part in content:
                if part['type'] == 'input_text':
                    parts.append({'type': 'text', 'text': part['text']})
                elif part['type'] == 'input_image':
                    url = part['image_url']
                    if not url.startswith('data:image/jpeg;base64,'):
                        raise ProviderFatal('DEEPSEEK_EXPECTED_JPEG_DATA_URL')
                    parts.append({'type': 'image', 'source': {
                        'type': 'base64', 'media_type': 'image/jpeg',
                        'data': url.split(',', 1)[1]}})
                else:
                    raise ProviderFatal('DEEPSEEK_UNSUPPORTED_INPUT')
            content = parts
        messages.append({'role': message['role'], 'content': content})
    # The public gateway example does not document JSON-schema response_format.
    # Supply the schema as instruction; ModelClient still validates the result.
    system.append('Return exactly one JSON object, without markdown or commentary, '
                  'matching this JSON Schema: ' + json.dumps(
                      payload['text']['format']['schema'], ensure_ascii=False))
    return {'model': model, 'max_tokens': payload['max_output_tokens'],
            'stream': False, 'thinking': {'type': 'disabled'},
            'system': '\n'.join(system), 'messages': messages}


def messages_response(raw):
    u = raw.get('usage') or {}
    inp, out = u.get('input_tokens'), u.get('output_tokens')
    cache_read = u.get('cache_read_input_tokens', 0)
    cache_write = u.get('cache_creation_input_tokens', 0)
    if any(type(v) is not int or v < 0 for v in (inp, out, cache_read, cache_write)):
        raise ProviderFatal('DEEPSEEK_USAGE_MISSING')
    # Anthropic input_tokens excludes cache reads/writes; include them once.
    text = ''.join(p.get('text', '') for p in raw.get('content', [])
                   if p.get('type') == 'text')
    return {'status': 'completed' if raw.get('stop_reason') == 'end_turn' and text else 'incomplete',
            'usage': {'input_tokens': inp + cache_read + cache_write, 'output_tokens': out,
                      'input_tokens_details': {'cached_tokens': cache_read,
                                               'cache_write_tokens': cache_write},
                      'resolved_model': raw.get('model'), 'provider_usage': u},
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}


def messages_request(endpoint, key, payload, model):
    global _retry_until
    req = Request(base_url(endpoint) + '/messages', data=encoded(messages_payload(payload, model)),
                  headers={'x-api-key': key, 'anthropic-version': '2023-06-01',
                           'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    for attempt in range(7):
        wait_for_gateway()
        try:
            with build_opener(NoRedirect()).open(req, timeout=120) as response:
                return messages_response(json.load(response))
        except HTTPError as error:
            if error.code == 429 and attempt < 6:
                delay = retry_delay(error.headers, attempt)
                error.close()
                with _cooldown_lock:
                    _retry_until = max(_retry_until, time.monotonic() + delay)
                print(f'DeepSeek HTTP 429: chờ {delay:.0f}s rồi thử lại ({attempt + 1}/6).', flush=True)
                continue
            # Never expose gateway response bodies or credentials. Unsupported
            # image requests stop the run rather than silently becoming NO.
            raise ProviderFatal(f'DEEPSEEK_HTTP_{error.code}: gateway từ chối; resume sau khi kiểm tra quota/giới hạn') from None
        except (URLError, TimeoutError, OSError):
            raise ProviderFatal('API_NETWORK_ERROR') from None
