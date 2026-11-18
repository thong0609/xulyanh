"""REST provider adapters. API credentials go in headers, never URL/log/output."""
import json
import math
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from approve_tool import CheckError, Ledger, atomic_json, encoded

PRICES = {('openai','gpt-5.4-mini'):(.75,4.5),
          ('openai','gpt-6-luna'):(.10,.50),
          ('gemini','gemini-2.5-flash-lite'):(.10,.40),
          ('gemini','gemini-3.5-flash-lite'):(.30,2.50),
          ('qwen','qwen3.7-flash'):(.20,.80)}

class ProviderFatal(RuntimeError): pass


def price_for(provider,model,custom_input=None,custom_output=None):
    if not re.fullmatch(r'[A-Za-z0-9._-]+',model):raise CheckError('Tên model không hợp lệ')
    if custom_input is not None or custom_output is not None:
        if any(v is None or not math.isfinite(v) or v<=0 for v in (custom_input,custom_output)):
            raise CheckError('Cung cấp cả input/output USD mỗi triệu token, giá phải dương')
        return custom_input,custom_output
    if (provider,model) not in PRICES:
        raise CheckError('Model chưa có giá: truyền --input-usd-per-million và --output-usd-per-million')
    return PRICES[provider,model]


class ProviderLedger(Ledger):
    def __init__(self,path,budget,rates,input_price_multiplier=1):
        super().__init__(path,budget);self.rates=rates
        self.input_price_multiplier=input_price_multiplier
    def reserve(self,amount):
        # Shared ModelClient bounds input/output at mini rates. Scale up if needed,
        # never downscale the safety reserve just because a new model is cheaper.
        return super().reserve(amount*max(1,self.rates[0]*self.input_price_multiplier/.75,self.rates[1]/4.5))
    def finish(self,idx,usage):
        with self.lock:
            cost=(usage['input_tokens']*self.rates[0]*self.input_price_multiplier+usage['output_tokens']*self.rates[1])/1e6
            self.data['calls'][idx]={'state':'reported','charged_or_reserved_usd':cost,'usage':usage}
            atomic_json(self.path,self.data)


def request_json(url,key,payload=None):
    req=Request(url,data=encoded(payload) if payload is not None else None,
                headers={'x-goog-api-key':key,'Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=90) as response:return json.load(response)
    except HTTPError as error:
        # Fail the run; do not turn inaccessible models/rate limits into blank rows.
        raise ProviderFatal(f'GEMINI_HTTP_{error.code}: kiểm tra model, key, quyền truy cập hoặc quota') from None
    except (URLError,OSError,TimeoutError):
        raise ProviderFatal('GEMINI_NETWORK_ERROR: request có thể đã được tính phí; xem usage trước khi resume') from None


def gemini_payload(payload,model):
    system='\n'.join(m['content'] for m in payload['input'] if m['role']=='system')
    parts=[]
    for message in payload['input']:
        if message['role']!='user':continue
        for part in message['content']:
            if part['type']=='input_text':parts.append({'text':part['text']})
            elif part['type']=='input_image':
                prefix,data=part['image_url'].split(',',1)
                mime=prefix.split(':',1)[1].split(';',1)[0]
                parts.append({'inlineData':{'mimeType':mime,'data':data}})
    config={'maxOutputTokens':payload['max_output_tokens'],
            'responseMimeType':'application/json','responseJsonSchema':payload['text']['format']['schema']}
    if model.startswith('gemini-2.5-'):config['thinkingConfig']={'thinkingBudget':0}
    elif model.startswith('gemini-3.'):config['thinkingConfig']={'thinkingLevel':'MINIMAL'}
    return {'systemInstruction':{'parts':[{'text':system}]},
            'contents':[{'role':'user','parts':parts}], 'generationConfig':config}


def gemini_response(raw):
    meta=raw.get('usageMetadata',{})
    inp=meta.get('promptTokenCount');cand=meta.get('candidatesTokenCount',0);thoughts=meta.get('thoughtsTokenCount',0)
    if type(inp) is not int or any(type(v) is not int or v<0 for v in (inp,cand,thoughts)):
        raise ProviderFatal('GEMINI_USAGE_MISSING: giữ reservation, không ghi nhãn record')
    candidates=raw.get('candidates',[])
    candidate=candidates[0] if candidates else {}
    parts=candidate.get('content',{}).get('parts',[])
    text=''.join(p.get('text','') for p in parts if not p.get('thought'))
    usage={'input_tokens':inp,'output_tokens':cand+thoughts,
           'input_tokens_details':{'cached_tokens':meta.get('cachedContentTokenCount',0)},
           'output_tokens_details':{'reasoning_tokens':thoughts},
           'provider_usage':meta,'resolved_model':raw.get('modelVersion')}
    return {'status':'completed' if candidate.get('finishReason')=='STOP' and text else 'incomplete',
            'usage':usage,'output':[{'type':'message','content':[{'type':'output_text','text':text}]}]}


def check_gemini(key,model):
    raw=request_json('https://generativelanguage.googleapis.com/v1beta/models/'+model,key)
    return {k:raw.get(k) for k in ('name','displayName','supportedGenerationMethods')}


def qwen_base_url(value):
    from urllib.parse import urlsplit
    p=urlsplit(value)
    if (p.scheme!='https' or not p.hostname or not p.hostname.endswith('.aliyuncs.com')
            or p.username or p.password or p.query or p.fragment or p.port not in (None,443)):
        raise CheckError('Qwen base URL phải là HTTPS endpoint Alibaba Cloud, không có key/query')
    if not p.path.rstrip('/').endswith('/compatible-mode/v1'):
        raise CheckError('Qwen base URL phải kết thúc bằng /compatible-mode/v1')
    return value.rstrip('/')


def qwen_request(base_url,key,payload):
    req=Request(qwen_base_url(base_url)+'/chat/completions',data=encoded(payload),
                headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=90) as response:return json.load(response)
    except HTTPError as error:raise ProviderFatal(f'QWEN_HTTP_{error.code}: kiểm tra key, region, model hoặc quota') from None
    except (URLError,OSError,TimeoutError):raise ProviderFatal('QWEN_NETWORK_ERROR: giữ reservation, kiểm tra trước khi resume') from None


def qwen_payload(payload,model):
    messages=[]
    for m in payload['input']:
        if m['role']=='system':messages.append({'role':'system','content':m['content']});continue
        content=[]
        for p in m['content']:
            if p['type']=='input_text':content.append({'type':'text','text':p['text']})
            elif p['type']=='input_image':content.append({'type':'image_url','image_url':{'url':p['image_url']}})
        messages.append({'role':'user','content':content})
    fmt=payload['text']['format']
    return {'model':model,'messages':messages,'enable_thinking':False,'stream':False,
            'max_tokens':payload['max_output_tokens'], 'response_format':{'type':'json_schema',
                'json_schema':{'name':fmt['name'],'schema':fmt['schema'],'strict':True}}}


def qwen_response(raw):
    usage=raw.get('usage',{})
    i,o=usage.get('prompt_tokens'),usage.get('completion_tokens')
    if any(type(v) is not int or v<0 for v in (i,o)):raise ProviderFatal('QWEN_USAGE_MISSING')
    choices=raw.get('choices',[]);choice=choices[0] if choices else {}
    text=choice.get('message',{}).get('content') or ''
    if not isinstance(text,str):raise ProviderFatal('QWEN_RESPONSE_INVALID')
    return {'status':'completed' if choice.get('finish_reason')=='stop' and text else 'incomplete',
            'usage':{'input_tokens':i,'output_tokens':o,'provider_usage':usage,'resolved_model':raw.get('model')},
            'output':[{'type':'message','content':[{'type':'output_text','text':text}]}]}
