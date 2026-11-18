#!/usr/bin/env python3
"""Cost-oriented local API runner. Default is offline; --run permits paid requests."""
import argparse
from http.client import InvalidURL
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import json
import os
from pathlib import Path
import threading
import time

from approve_tool import (ROOT, MODEL, VERSION, ModelClient, Fetcher, Ledger, BudgetExceeded,
    CheckError, atomic_json, digest, encoded, read_csv, export_csv, within, run_lock, load_env,
    evidence_present, Pipeline, baseline_sample)
from matching import profile_name, exact_match

from api_providers import (ProviderLedger, ProviderFatal, price_for, gemini_payload,
                           gemini_response, request_json, check_gemini, qwen_payload, qwen_response, qwen_request, qwen_base_url)

ECONOMY_VERSION = 'api-economy-v2-providers'


# Verified predecessor differs only in runner scheduling/runtime settings.
# Do not carry this exception forward when changing classification policy.
COMPATIBLE_RUNNER_HASHES = {
    '60d71dd526fe7519b7e0c1ca93943d3f6110a397ccd4c73417f920a7d21b8ce4',
    '25384d4b6da831b53e2b393b0d4da690fd5d85f174bd572ed8de47b73d53c8bd',
}
PRE_PARALLEL_DEPENDENCIES = 'ec9bb05c6c493323d8f20b630583e1779faefd3a07c87311a469fd189fd92fe0'


def compatible_resume(previous, current):
    if current['budget_usd'] < previous.get('budget_usd',0): return False
    ignored={'budget_usd','workers','code_sha256'}
    if any(previous.get(k)!=v for k,v in current.items() if k not in ignored):return False
    if previous.get('code_sha256')==current['code_sha256']:return True
    dependencies=digest(encoded({n:digest((ROOT/n).read_bytes()) for n in
                                ('api_providers.py','approve_tool.py','matching.py','source_page.py')}))
    return (previous.get('code_sha256') in COMPATIBLE_RUNNER_HASHES
            and dependencies==PRE_PARALLEL_DEPENDENCIES)


class StopBudget(RuntimeError): pass


class EconomyClient(ModelClient):
    max_output_tokens = 900
    def __init__(self, key, ledger, cache, transport=None, provider='openai', model=MODEL, base_url=None, original_prompts=False):
        self.original_prompts=original_prompts
        if original_prompts:self.max_output_tokens=1800
        scope=Path(cache)/digest(encoded([ECONOMY_VERSION,provider,model,base_url,self.max_output_tokens]))
        super().__init__(key, ledger, scope, transport)
        self.locks = [threading.Lock() for _ in range(64)]
        self.hits = 0
        self.provider,self.model,self.base_url=provider,model,base_url

    def _post(self, payload):
        payload['max_output_tokens'] = self.max_output_tokens
        for message in payload['input']:
            if isinstance(message.get('content'),list):
                for part in message['content']:
                    if part.get('type') == 'input_text':
                        part['text'] = json.dumps(json.loads(part['text']),ensure_ascii=False,separators=(',',':'))
        payload['model']=self.model
        if self.provider=='qwen':
            return qwen_response(qwen_request(self.base_url,self.key,qwen_payload(payload,self.model)))
        if self.provider=='gemini':
            raw=request_json('https://generativelanguage.googleapis.com/v1beta/models/'+
                             self.model+':generateContent',self.key,gemini_payload(payload,self.model))
            return gemini_response(raw)
        try:return super()._post(payload)
        except CheckError as error:raise ProviderFatal(str(error)) from None

    def ask(self, task, instruction, data, output_schema, image=None):
        # OCR is independent of the query entity. Reuse only the identical old OCR prompt.
        original = digest(encoded([VERSION,MODEL,task,instruction,data,digest(image) if image else None]))
        old = ROOT/'cache/model'/(original+'.json')
        if task == 'observe' and self.provider=='openai' and self.model==MODEL and old.exists():
            value = json.loads(old.read_text())
            if (value.get('status') in ('readable','no_text','unreadable') and isinstance(value.get('texts'),list)
                    and all(isinstance(t,str) for t in value['texts'])):
                self.hits += 1
                return value
        if not self.original_prompts:
            instruction += ' Keep explanation to one short sentence. Do not omit text, evidence or required fields.'
        key = digest(encoded([task,instruction,data,output_schema,digest(image) if image else None]))
        with self.locks[int(key[:8],16) % len(self.locks)]:
            cache_key = digest(encoded([VERSION,MODEL,task,instruction,data,digest(image) if image else None]))
            if (self.cache/(cache_key+'.json')).exists(): self.hits += 1
            try: return super().ask(task,instruction,data,output_schema,image)
            except BudgetExceeded as e: raise StopBudget(str(e)) from None


class ResilientFetcher(Fetcher):
    def fetch(self, url, kind):
        try:return super().fetch(url,kind)
        except InvalidURL:
            # Can originate from the original URL or a malformed redirect Location.
            # Let the pipeline continue other evidence checks; never label no from this error.
            raise CheckError('FETCH_INVALID_URL') from None


class EconomyPipeline:
    def __init__(self, client, fetcher, overrides=None):
        self.client,self.fetcher,self.overrides=client,fetcher,overrides or {}

    def process(self,row,row_id,index):
        p=profile_name(row['entity_name'],self.overrides.get(row['entity_id']))
        r=dict(row_id=row_id,row_index=index,entity_name=row['entity_name'],approve='',
               reason='CHECK_INCOMPLETE',checks={},errors=[],profile=p)
        def finish(label,reason): r.update(approve=label,reason=reason);return r
        for field in ('image_url','page_url'):
            hit=exact_match(p,row[field])
            if hit:
                r['checks'][field]=hit
                return finish('yes',field.upper()+'_NAME_MATCH')
        image=None;obs=None;texts=[]
        try:
            image=self.fetcher.image(row['image_url'])
            obs=self.client.observe(image);r['checks']['image_observation']=obs
            texts=obs['texts']
            for size in (1,2,3):
                for start in range(len(texts)-size+1):
                    lines=texts[start:start+size]
                    if size>1 and not all(t.strip() and len(t)<=60 for t in lines):continue
                    hit=exact_match(p,' '.join(lines))
                    if hit:
                        r['checks']['image_match']={**hit,'status':'match','evidence':' '.join(lines),
                            'source_lines':lines,'source_line_indices':list(range(start,start+size))}
                        return finish('yes','IMAGE_NAME_MATCH')
        except (CheckError,OSError) as e:r['errors'].append({'step':'image','error':str(e)})
        combined=None
        try:
            combined=self.client.compare(p,texts+[row['image_url'],row['page_url']],
                f'First {len(texts)} blocks are visible image text; final 2 blocks are URL strings. '
                'IDs, dates and image sizes in URLs are not entity names. Check actual observed text only.')
            r['checks']['combined_name_match']=combined
            if combined['status']=='match':
                name=combined.get('observed_name','')
                origin='IMAGE_NAME_MATCH' if name and evidence_present(name,texts) else 'URL_SEMANTIC_NAME_MATCH'
                return finish('yes',origin)
        except (CheckError,OSError) as e:r['errors'].append({'step':'combined_names','error':str(e)})
        try:
            page=self.fetcher.page(row['page_url'],row['image_url'])
            r['checks']['page']=page
            if page['incomplete']:raise CheckError('PAGE_EXTRACTION_INCOMPLETE')
            decision=(self.client.assess_page(p,page,image=image) if p.get('scope')=='group'
                      else self.client.assess_page(p,page))
            r['checks']['page_match']=decision
            if decision['status']=='match':
                return finish('yes','PAGE_RELATION_MATCH' if decision.get('relation') in
                              ('instance_of','part_of') else 'PAGE_SECTION_MATCH')
            if decision['status']=='other_entity':return finish('no','PAGE_SECTION_OTHER_ENTITY')
            if (decision['status']=='name_not_found' and obs and obs['status'] in ('readable','no_text')
                    and combined and combined['status']=='not_match' and p.get('scope')!='group'):
                return finish('no','NAME_NOT_FOUND')
        except (CheckError,OSError) as e:r['errors'].append({'step':'page','error':str(e)})
        return r


def selection(rows,first,start_row=1):
    # Limit physical CSV data rows BEFORE filtering labels, never refill from later rows.
    return [i for i in range(start_row-1,min(start_row-1+first,len(rows))) if not rows[i]['approve'].strip()]


def estimate(rows,selected,overrides):
    hits=[i for i in selected if any(exact_match(profile_name(rows[i]['entity_name'],
          overrides.get(rows[i]['entity_id'])),rows[i][f]) for f in ('image_url','page_url'))]
    hit_set=set(hits)
    remaining=[i for i in selected if i not in hit_set]
    pilot=json.loads((ROOT/'outputs/pilot_v2_2/summary.json').read_text())
    unit=pilot['charged_or_reserved_usd']/pilot['processed']
    # Scenarios, not a token quote: compare residual cost to historical per-row average.
    return {'mode':'offline scenario estimate, no API calls', 'selected':len(selected),
        'url_rule_matches':len(hits),'requires_further_checks':len(remaining),
        'distinct_remaining_image_urls':len({rows[i]['image_url'] for i in remaining}),
        'historical_usd_per_row':unit,'unchanged_pipeline_extrapolation_usd':round(len(selected)*unit,3),
        'scenario_usd':{'optimistic_residual_60pct':round(len(remaining)*unit*.6,3),
                        'planning_residual_100pct':round(len(remaining)*unit,3),
                        'cautious_residual_150pct':round(len(remaining)*unit*1.5,3)},
        'assumptions':'Scenarios apply 60/100/150% of historical average per residual row. '
          'Not measured optimized usage; preschool-only first rows differ from pilot mix. '
          'Cache discounts not assumed. Budget cap can stop before completion.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'input/general_10m_part_02_copy.csv')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'outputs/api_economy_first_2000')
    parser.add_argument('--provider',choices=['openai','gemini','qwen'],default='openai')
    parser.add_argument('--model',help='Exact API model ID')
    parser.add_argument('--qwen-base-url',help='Alibaba Cloud compatible-mode/v1 endpoint from console')
    parser.add_argument('--input-usd-per-million',type=float)
    parser.add_argument('--output-usd-per-million',type=float)
    parser.add_argument('--check-model',action='store_true',help='Gemini model metadata only, no inference')
    parser.add_argument('--start-row',type=int,default=1,help='First CSV data row, 1-based')
    select=parser.add_mutually_exclusive_group()
    select.add_argument('--first',type=int,default=2000)
    select.add_argument('--baseline-dir',type=Path,help='Reuse exact records from a completed run')
    parser.add_argument('--pipeline',choices=['economy','v2.2'],default='economy')
    parser.add_argument('--budget-usd',type=float,default=10)
    parser.add_argument('--workers',type=int,default=3,help='Concurrent records, 1–16; try 8 for paid API')
    parser.add_argument('--save-every',type=int,default=25)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args(argv)
    if min(args.start_row,args.first,args.budget_usd,args.workers,args.save_every)<=0 or args.workers>16:
        raise CheckError('Giới hạn phải dương, workers tối đa 16')
    args.model=args.model or {'openai':MODEL,'gemini':'gemini-3.5-flash-lite','qwen':'qwen3.7-flash'}[args.provider]
    if args.provider=='qwen':
        if not args.qwen_base_url:raise CheckError('Qwen cần --qwen-base-url từ Alibaba Cloud console')
        args.qwen_base_url=qwen_base_url(args.qwen_base_url)
    rates=price_for(args.provider,args.model,args.input_usd_per_million,args.output_usd_per_million)
    if args.check_model:
        if args.provider!='gemini':raise CheckError('--check-model hiện dùng cho Gemini')
        load_env(ROOT/'.env')
        key=os.environ.get('GEMINI_API_KEY','').strip()
        if not key:raise CheckError('Điền GEMINI_API_KEY trong tool/.env')
        print(json.dumps(check_gemini(key,args.model),ensure_ascii=False,indent=2));return 0
    source=within(args.input,ROOT/'input');output=within(args.output_dir,ROOT/'outputs')
    rows,fields,ids,encoding,newline,sha=read_csv(source)
    overrides=json.loads((ROOT/'name_overrides.json').read_text())
    baseline_folder=within(args.baseline_dir,ROOT/'outputs') if args.baseline_dir else None
    baseline_hash=None
    if baseline_folder:
        if args.start_row!=1:raise CheckError('--start-row không dùng với --baseline-dir')
        if output==baseline_folder or output.is_relative_to(baseline_folder) or baseline_folder.is_relative_to(output):
            raise CheckError('Output phải tách riêng baseline')
        bm=json.loads((baseline_folder/'manifest.json').read_text())
        selected,_=baseline_sample(baseline_folder,sha,rows,ids,len(bm.get('selected_indices',[])))
        if not selected:raise CheckError('Baseline không có record')
        baseline_hash=digest((baseline_folder/'results.jsonl').read_bytes())
    else:selected=selection(rows,args.first,args.start_row)
    manifest={'version':ECONOMY_VERSION,'input_sha256':sha,'rows':len(rows),'first':args.first,'start_row':args.start_row,
        'pipeline':args.pipeline,'baseline_results_sha256':baseline_hash,
        'selected_indices':selected,'provider':args.provider,'model':args.model,'rates_per_million':list(rates),'qwen_base_url':args.qwen_base_url,'budget_usd':args.budget_usd,'workers':args.workers,
        'overrides_sha256':digest(encoded(overrides)), 'max_output_tokens':1800 if args.pipeline=='v2.2' else EconomyClient.max_output_tokens,
        'reasoning_effort':'none',
        'input_price_multiplier':1.25 if args.model=='gpt-6-luna' and args.provider=='openai' else 1,
        'code_sha256':digest(encoded({n:digest((ROOT/n).read_bytes()) for n in
            ('api_economy.py','api_providers.py','approve_tool.py','matching.py','source_page.py')}))}
    output.mkdir(parents=True,exist_ok=True)
    with run_lock(output/'.lock'):
        report=estimate(rows,selected,overrides)
        report['provider']=args.provider;report['model']=args.model
        report['rates_per_million']=list(rates)
        if args.provider!='openai' or args.model!=MODEL:
            pilot_usage=json.loads((ROOT/'outputs/pilot_v2_2/usage.json').read_text())['calls']
            inp=sum(c['usage']['input_tokens'] for c in pilot_usage)
            out=sum(c['usage']['output_tokens'] for c in pilot_usage)
            report['same_token_workload_extrapolation_usd']=round(
                (inp*rates[0]+out*rates[1])/1e6*len(selected)/50,4)
            report['scenario_usd']=None
            report['assumptions']='Price-only extrapolation of old OpenAI tokens; provider image tokens, '
            report['assumptions']+='thinking/output length and new pipeline workload differ. Not a cost guarantee.'
        if not args.run:
            atomic_json(output/'cost_estimate.json',report)
            atomic_json(output/'selection_preview.json',manifest)
            print(json.dumps(report,ensure_ascii=False,indent=2));return 0
        old=output/'manifest.json'
        if old.exists():
            previous=json.loads(old.read_text())
            compatible=compatible_resume(previous,manifest)
            if not args.resume or not compatible:
                raise CheckError('Run đã tồn tại hoặc cấu hình khác; resume giữ policy/input/model, có thể đổi workers hoặc tăng ngân sách')
        elif args.resume:raise CheckError('Chưa có run để resume')
        load_env(ROOT/'.env')
        key_name={'gemini':'GEMINI_API_KEY','openai':'OPENAI_API_KEY','qwen':'DASHSCOPE_API_KEY'}[args.provider]
        key=os.environ.get(key_name,'').strip()
        if not key:raise CheckError('Điền '+key_name+' trong tool/.env')
        import PIL  # Verify image support before starting paid work.
        atomic_json(old,manifest)
        ledger=ProviderLedger(output/'usage.json',args.budget_usd,rates,
                              input_price_multiplier=manifest['input_price_multiplier'])
        namespace=digest(encoded([ECONOMY_VERSION,args.provider,args.model,args.pipeline,manifest['max_output_tokens']]))
        client=EconomyClient(key,ledger,ROOT/'cache/api_models'/namespace,
                             provider=args.provider,model=args.model,base_url=args.qwen_base_url,original_prompts=args.pipeline=='v2.2')
        pipeline_class=Pipeline if args.pipeline=='v2.2' else EconomyPipeline
        pipeline=pipeline_class(client,ResilientFetcher(ROOT/'cache/http'),overrides)
        results={};journal_path=output/'results.jsonl'
        if journal_path.exists():
            raw=journal_path.read_bytes()
            if raw and not raw.endswith(b'\n'):
                raw=raw[:raw.rfind(b'\n')+1];journal_path.write_bytes(raw)
            for line in raw.splitlines():
                r=json.loads(line);i=r['row_index']
                if i not in selected or r['row_id']!=ids[i] or i in results:raise CheckError('Checkpoint mismatch')
                results[i]=r
        pending=iter(i for i in selected if i not in results)
        initial_count=len(results)
        started=time.monotonic();stop_reason=None
        def save():
            if digest(source.read_bytes())!=sha:raise CheckError('Input changed')
            export_csv(output/'reviewed.csv',rows,fields,results,encoding,newline)
            if not baseline_folder and args.start_row==1:
                export_csv(output/'first_rows.csv',rows[:args.first],fields,results,encoding,newline)
            export_csv(output/'selected_rows.csv',[rows[i] for i in selected],fields,
                       {n:results[i] for n,i in enumerate(selected) if i in results},encoding,newline)
            atomic_json(output/'summary.json',{'selected':len(selected),'completed':len(results),
                'remaining':len(selected)-len(results),'complete':len(results)==len(selected),
                'stop_reason':stop_reason,'counts':dict(Counter(r['approve'] or 'blank' for r in results.values())),
                'elapsed_seconds_this_session':round(time.monotonic()-started,2),
                'workers':args.workers,
                'processed_this_session':len(results)-initial_count,
                'rows_per_hour_this_session':round((len(results)-initial_count)*3600/max(time.monotonic()-started,.001),2),
                'cache_hits_this_session':client.hits,**ledger.report()})
        active={}
        with journal_path.open('a',encoding='utf-8') as journal,ThreadPoolExecutor(max_workers=args.workers) as pool:
            def fill():
                while not stop_reason and len(active)<args.workers:
                    i=next(pending,None)
                    if i is None:break
                    active[pool.submit(pipeline.process,rows[i],ids[i],i)]=i
            try:
                fill()
                while active:
                    ready,_=wait(active,return_when=FIRST_COMPLETED)
                    for f in ready:
                        i=active.pop(f)
                        try:r=f.result()
                        except StopBudget:stop_reason='BUDGET_LIMIT';continue
                        except ProviderFatal as e:stop_reason=str(e);continue
                        except Exception as e:
                            stop_reason='INTERNAL_ERROR: '+type(e).__name__;continue
                        journal.write(json.dumps(r,ensure_ascii=False)+'\n');journal.flush();os.fsync(journal.fileno())
                        results[i]=r
                        if len(results)%args.save_every==0:save()
                        print(f'{len(results)}/{len(selected)} | {r["approve"] or "blank"} | '
                              f'cost<=${ledger.total():.4f}',flush=True)
                    fill()
            except KeyboardInterrupt:
                stop_reason='INTERRUPTED'
                for f in active:f.cancel()
            finally:
                # Join before final summary so usage includes every in-flight request.
                pool.shutdown(wait=True,cancel_futures=True)
                save()
        print('Output:',output)
        return 2 if stop_reason else 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (CheckError,ProviderFatal,OSError) as e:print('LỖI:',e);raise SystemExit(2)
