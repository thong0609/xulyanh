"""Chat Completions transport for the explicitly configured intermediary endpoint."""
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from approve_tool import CheckError, encoded
from api_providers import ProviderFatal


def base_url(value):
    p = urlsplit(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise CheckError('Base URL phải là HTTPS, không chứa key, query hoặc fragment')
    return value.rstrip('/')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def chat_payload(payload):
    messages = []
    for message in payload['input']:
        content = message['content']
        if isinstance(content, list):
            converted = []
            for part in content:
                if part['type'] == 'input_text':
                    converted.append({'type': 'text', 'text': part['text']})
                elif part['type'] == 'input_image':
                    converted.append({'type': 'image_url', 'image_url': {
                        'url': part['image_url'], 'detail': part.get('detail', 'high')}})
                else:
                    raise ProviderFatal('CHAT_UNSUPPORTED_INPUT')
            content = converted
        messages.append({'role': message['role'], 'content': content})
    fmt = payload['text']['format']
    return {'model': payload['model'], 'messages': messages, 'stream': False,
            'max_completion_tokens': payload['max_output_tokens'],
            'reasoning_effort': 'none',
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': fmt['name'], 'schema': fmt['schema'], 'strict': True}}}


def chat_response(raw):
    usage = raw.get('usage') or {}
    inp, out = usage.get('prompt_tokens'), usage.get('completion_tokens')
    if any(type(v) is not int or v < 0 for v in (inp, out)):
        raise ProviderFatal('CHAT_USAGE_MISSING')
    choices = raw.get('choices') or []
    choice = choices[0] if choices else {}
    text = (choice.get('message') or {}).get('content') or ''
    if not isinstance(text, str):
        raise ProviderFatal('CHAT_RESPONSE_INVALID')
    return {'status': 'completed' if choice.get('finish_reason') == 'stop' and text else 'incomplete',
            'usage': {'input_tokens': inp, 'output_tokens': out,
                      'input_tokens_details': usage.get('prompt_tokens_details') or {},
                      'output_tokens_details': usage.get('completion_tokens_details') or {},
                      'resolved_model': raw.get('model')},
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}


def chat_request(endpoint, key, payload):
    req = Request(base_url(endpoint)+'/chat/completions', data=encoded(chat_payload(payload)),
                  headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json',
                           'User-Agent': 'Mozilla/5.0'})
    try:
        with build_opener(NoRedirect()).open(req, timeout=90) as response:
            return chat_response(json.load(response))
    except HTTPError as error:
        details = []
        try:
            info = json.loads(error.read(65536)).get('error') or {}
            for field in ('code', 'type', 'param'):
                value = info.get(field)
                if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', value):
                    details.append(field+'='+value)
        except (ValueError, AttributeError, TypeError):
            pass
        suffix = ': '+'; '.join(details) if details else ''
        raise ProviderFatal(f'CHAT_HTTP_{error.code}'+suffix) from None
    except (URLError, TimeoutError, OSError):
        raise ProviderFatal('CHAT_NETWORK_ERROR: kiểm tra trước khi resume') from None
