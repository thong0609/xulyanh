#!/usr/bin/env python3
"""Standard API only: grouped Luna, parallel image groups, immutable input. Offline by default."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from datetime import datetime,timezone
import json
from pathlib import Path
import os
import time
from approve_tool import ROOT,CheckError,read_csv,digest,encoded,atomic_json,export_csv,run_lock,load_env,within
from api_economy import EconomyClient,ResilientFetcher,StopBudget
from api_providers import ProviderLedger,ProviderFatal,price_for
from grouped_pipeline import GroupPipeline,image_groups,common_brand
from matching import profile_name,exact_match

VERSION='luna-groups-standard-v4'


class StandardFetcher(ResilientFetcher):
    def fetch(self,url,kind):
        try:return super().fetch(url,kind)
        except UnicodeEncodeError:
            # A Unicode URL/redirect unsupported by urllib is a failed check, not a fatal run error.
            raise CheckError('FETCH_URL_ENCODING_ERROR') from None


class StandardClient(EconomyClient):
    def _post(self,payload):
        try:return super()._post(payload)
        except ProviderFatal as error:
            # The shared transport suppresses the traceback, but retains HTTPError in
            # __context__. Extract only safe error codes, never raw messages or credentials.
            if str(error)!='API_HTTP_429':raise
            from urllib.error import HTTPError
            import re
            context=error;seen=set();details=[]
            while context is not None and id(context) not in seen:
                seen.add(id(context))
                if isinstance(context,HTTPError):
                    try:
                        body=json.loads(context.read(65536));info=body.get('error',{})
                        for name in ('code','type'):
                            value=info.get(name)
                            if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',value):
                                details.append(name+'='+value)
                        retry=context.headers.get('Retry-After','')
                        if re.fullmatch(r'\d+(?:\.\d+)?',retry):details.append('retry_after_seconds='+retry)
                    except (ValueError,TypeError,AttributeError,OSError):pass
                    break
                context=context.__context__
            if details:raise ProviderFatal('API_HTTP_429: '+'; '.join(details)) from None
            raise

    def ask(self,*args,**kwargs):
        try:return super().ask(*args,**kwargs)
        except UnicodeEncodeError:
            # Model JSON can contain an unpaired surrogate: preserve any usage reservation,
            # stop this evidence check and let the pipeline retain an unresolved label.
            raise CheckError('MODEL_UNICODE_ENCODING_ERROR') from None


def runtime_compatible(previous,current):
    ignored=('workers','budget_usd','code_sha256')
    if any(previous.get(k)!=v for k,v in current.items() if k not in ignored):return False
    if current['budget_usd']<previous['budget_usd']:return False
    if previous['code_sha256']==current['code_sha256']:return True
    # Each audited runtime-only change is pinned to BOTH complete code hashes.
    path=ROOT/'standard_runtime_compatibility.json'
    upgrades=json.loads(path.read_text()) if path.exists() else []
    return any(x['from']==previous['code_sha256'] and x['to']==current['code_sha256'] for x in upgrades)



def select_seed(rows,start_row,first,unlabeled_only=False):
    candidates=range(start_row-1,len(rows))
    if unlabeled_only:candidates=(i for i in candidates if not rows[i].get('approve','').strip())
    from itertools import islice
    return list(islice(candidates,first))


def run(args,client_factory=StandardClient,fetcher_factory=StandardFetcher,batch_api_factory=None):
    execution='standard'
    if getattr(args,'execution','standard')!='standard':raise CheckError('Runner này chỉ dùng Standard API')
    source=args.input.resolve()
    if source.is_relative_to(ROOT.parent/'done'):raise CheckError('Không dùng/ghi file done cho chế độ này')
    output=within(args.output_dir,ROOT/'outputs');output.mkdir(parents=True,exist_ok=True)
    rates=price_for('openai',args.model)
    with run_lock(output/'.lock'):
        snapshot=output/'input_snapshot.csv';manifest_path=output/'manifest.json'
        old=json.loads(manifest_path.read_text()) if manifest_path.exists() else None
        if args.resume and not old:raise CheckError('Chưa có run để resume')
        if old and not args.resume:raise CheckError('Run đã tồn tại; dùng --resume hoặc output mới')
        if old:
            raw=snapshot.read_bytes()
            if digest(raw)!=old['input_sha256']:raise CheckError('Snapshot checkpoint bị thay đổi')
        else:raw=source.read_bytes()
        # Parse a temporary snapshot in output even for offline inspection; no main CSV edits.
        if not old:
            if snapshot.exists() and snapshot.read_bytes()!=raw:raise CheckError('Preview snapshot khác nguồn; dùng output mới')
            if not snapshot.exists():snapshot.write_bytes(raw)
        rows,fields,ids,enc,newline,sha=read_csv(snapshot)
        baseline_dir=getattr(args,'baseline_dir',None)
        baseline_sha=None
        if baseline_dir and getattr(args,'unlabeled_only',False):
            raise CheckError('Không dùng --unlabeled-only cùng --baseline-dir')
        if baseline_dir:
            baseline=json.loads((baseline_dir/'manifest.json').read_text())
            seed=baseline.get('selected_indices')
            if baseline.get('input_sha256')!=sha:raise CheckError('Pilot dùng CSV khác; chọn đúng --input của pilot cũ')
            if (not isinstance(seed,list) or not seed or len(set(seed))!=len(seed)
                    or any(type(i) is not int or not 0<=i<len(rows) for i in seed)):
                raise CheckError('Pilot selected_indices không hợp lệ')
            result_bytes=(baseline_dir/'results.jsonl').read_bytes();seen=set()
            for line in result_bytes.splitlines():
                value=json.loads(line);i=value['row_index']
                if i not in seed or i in seen or value['row_id']!=ids[i]:raise CheckError('Pilot row identity mismatch')
                seen.add(i)
            if seen!=set(seed):raise CheckError('Pilot chưa hoàn thành đủ record')
            baseline_sha=digest(result_bytes)
        else:
            seed=select_seed(rows,args.start_row,args.first,getattr(args,'unlabeled_only',False))
        if not seed:raise CheckError('Không có dòng trong phạm vi yêu cầu')
        selected,groups=image_groups(rows,seed)
        overrides=json.loads((ROOT/'name_overrides.json').read_text())
        improved=getattr(args,'policy','legacy')=='user-rules-v5'
        dependencies=('run_grouped_luna_standard.py','grouped_pipeline.py','grouped_user_rules.py','address_rules.py','api_economy.py','api_providers.py',
                 'approve_tool.py','matching.py','source_page.py')
        if improved:dependencies+=('source_subject_guard.py','group_aliases.py','propagate_group_yes.py')
        manifest={'version':'luna-groups-standard-v5' if improved else VERSION,'decision_policy':getattr(args,'policy','legacy'),'group_yes':getattr(args,'group_yes','multiple'),'execution':execution,'model':args.model,'source':str(source),'input_sha256':sha,
            'rows':len(rows),'start_row':args.start_row,'first':args.first,'selected_indices':selected,
            'seed_indices':seed,'unlabeled_only':getattr(args,'unlabeled_only',False),'baseline_results_sha256':baseline_sha,'groups':len(groups),'workers':args.workers,'budget_usd':args.budget_usd,
            'rates':list(rates),'overrides_sha256':digest(encoded(overrides)),
            'code_sha256':digest(encoded({n:digest((ROOT/n).read_bytes()) for n in dependencies}))}
        if old and not runtime_compatible(old,manifest):raise CheckError('Policy/input/config thay đổi; không resume lẫn run')
        stats={'seed_rows':len(seed),'expanded_selected_rows':len(selected),'image_groups':len(groups),
            'groups_with_existing_yes':sum(any(rows[i]['approve']=='yes' for i in g) for g in groups),
            'rule':('user rules v5; found image with empty text yes; image unconfirmed/errors pending; explicit conflicts first; compatible aliases yes' if improved else
                    'user rules v4; model decisions first; missing image context yes; other check errors no; '+getattr(args,'group_yes','multiple')+' fallback yes'
                    if getattr(args,'policy','legacy')=='user-rules-v4' else 'existing first yes; else prefer unique image-linked address; else first brand representative'),
            'source':str(source),'snapshot':str(snapshot),'api_calls':0,'billing_mode':execution}
        atomic_json(output/'selection_preview.json',{**stats,'manifest':manifest})
        if not args.run:
            print(json.dumps(stats,ensure_ascii=False,indent=2));return 0
        load_env(ROOT/'.env');key=os.environ.get('OPENAI_API_KEY','').strip()
        if not key:raise CheckError('Điền OPENAI_API_KEY trong tool/.env')
        import PIL
        if old and old['code_sha256']!=manifest['code_sha256']:
            atomic_json(output/'runtime_upgrade.json',{'from':old['code_sha256'],'to':manifest['code_sha256'],
                'reason':'Audited Standard runtime update; input, selection and decision policy unchanged'})
        atomic_json(manifest_path,manifest)
        ledger=ProviderLedger(output/'usage.json',args.budget_usd,rates,
            input_price_multiplier=1.25 if args.model=='gpt-6-luna' else 1)
        client=client_factory(key,ledger,ROOT/'cache/grouped_api',provider='openai',model=args.model)
        engine_class=GroupPipeline
        if getattr(args,'policy','legacy') in ('user-rules-v4','user-rules-v5'):
            from grouped_user_rules import UserRulesGroupPipeline
            engine_class=UserRulesGroupPipeline
        engine_options={'require_ocr_response':True}
        if getattr(args,'policy','legacy') in ('user-rules-v4','user-rules-v5'):
            engine_options['one_yes_per_image']=getattr(args,'group_yes','multiple')=='single'
        if improved:
            engine_options['improved_rules']=True
            from source_subject_guard import SourceSubjectClient
            if not isinstance(client,SourceSubjectClient):client=SourceSubjectClient(client)
        engine=engine_class(client,fetcher_factory(ROOT/'cache/http'),overrides,**engine_options)
        results={};journal_path=output/'results.jsonl'
        if journal_path.exists():
            data=journal_path.read_bytes()
            if data and not data.endswith(b'\n'):
                data=data[:data.rfind(b'\n')+1];journal_path.write_bytes(data)
            for line in data.splitlines():
                r=json.loads(line);i=r['row_index']
                if i not in selected or r['row_id']!=ids[i] or i in results:raise CheckError('Journal identity mismatch')
                results[i]=r
        pending=iter(g for g in groups if any(i not in results for i in g))
        start=time.monotonic();initial=len(results);stop=None;active={};completed_groups=0;network_deferred=[]
        def defer_group(group,reason):
            network_deferred.append(group)
            if getattr(engine,'records_deferred',False):return
            with (output/'deferred_groups.jsonl').open('a') as log:
                log.write(json.dumps({'row_indices':group,'error':reason,'attempts':1,
                    'timestamp':time.time(),'action':'deferred_without_label'})+'\n')
            print(f'{len(results)}/{len(selected)} records | group {len(group)} | cost<=${ledger.total():.4f} | skip {reason}',flush=True)
        def save():
            export_csv(output/'reviewed.csv',rows,fields,results,enc,newline)
            export_csv(output/'selected_rows.csv',[rows[i] for i in selected],fields,
                       {n:results[i] for n,i in enumerate(selected) if i in results},enc,newline)
            atomic_json(output/'summary.json',{'selected':len(selected),'seed_rows':len(seed),
                'completed':len(results),'remaining':len(selected)-len(results),'complete':len(results)==len(selected),
                'image_groups':len(groups),'counts':dict(Counter(r['approve'] or 'blank' for r in results.values())),
                'billing_mode':'standard','stop_reason':stop,
                'network_deferred_groups':len(network_deferred),'network_deferred_row_indices':network_deferred,
                'processed_this_session':len(results)-initial,
                'elapsed_seconds_this_session':round(time.monotonic()-start,2),**ledger.report()})
        with ThreadPoolExecutor(max_workers=args.workers) as pool,journal_path.open('a',encoding='utf-8') as journal:
            def fill():
                while not stop and len(active)<args.workers:
                    group=next(pending,None)
                    if group is None:break
                    items=[(i,dict(rows[i],approve=results[i]['approve']) if i in results else rows[i],ids[i]) for i in group]
                    active[pool.submit(engine.process_group,items)]=group
            try:
                fill()
                while active:
                    ready,_=wait(active,return_when=FIRST_COMPLETED)
                    for future in ready:
                        group=active.pop(future)
                        try:answers=future.result()
                        except StopBudget:stop='BUDGET_LIMIT';continue
                        except ProviderFatal as error:
                            if improved and not any(code in str(error) for code in (
                                    'HTTP_401','HTTP_402','HTTP_403','HTTP_429','insufficient_quota')):
                                defer_group(group,str(error));continue
                            if str(error)=='API_NETWORK_ERROR':
                                network_deferred.append(group)
                                print(f'NETWORK_ERROR: tạm bỏ {len(group)} record, tiếp tục nhóm khác; resume sau để thử lại.',flush=True)
                                continue
                            stop=str(error);continue
                        except Exception as error:stop='INTERNAL_ERROR: '+type(error).__name__;continue
                        if {r['row_index'] for r in answers}!=set(group):
                            stop='GROUP_RESULT_MISMATCH';continue
                        if improved:
                            failures=[e['error'] for r in answers for e in r.get('errors',[])]
                            if failures or any(r['approve'] not in ('yes','no') for r in answers):
                                reason=failures[0] if failures else 'CHECK_INCOMPLETE'
                                defer_group(group,reason)
                                continue
                        # Journal an entire group together; partial tail is recoverable on resume.
                        fresh=[r for r in answers if r['row_index'] not in results]
                        journal.write(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in fresh))
                        journal.flush();os.fsync(journal.fileno())
                        for r in fresh:results[r['row_index']]=r
                        completed_groups+=1
                        print(f'{len(results)}/{len(selected)} records | group {len(group)} | cost<=${ledger.total():.4f}',flush=True)
                        if completed_groups%args.save_every==0:save()
                    fill()
            except KeyboardInterrupt:
                stop='INTERRUPTED'
                for f in active:f.cancel()
            finally:
                pool.shutdown(wait=True,cancel_futures=True)
                if not stop and network_deferred:stop='NETWORK_GROUPS_PENDING_RESUME'
                save()
        print('Output:',output);return 2 if stop else 0


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT.parent/'general_10m_part_02.csv')
    p.add_argument('--output-dir',type=Path,default=ROOT/'outputs/luna_grouped_standard_rules_v5_2000')
    p.add_argument('--baseline-dir',type=Path,help='Lấy seed đúng các record của pilot đã hoàn thành; vẫn mở rộng nhóm ảnh')
    p.add_argument('--unlabeled-only',action='store_true',help='Lấy đủ --first dòng approve trống theo thứ tự CSV, rồi mở rộng nhóm ảnh')
    p.add_argument('--group-yes',choices=('multiple','single'),default='multiple',help='V4: nhiều yes theo rule, hoặc ép mỗi ảnh một yes')
    p.add_argument('--policy',choices=('user-rules-v5','user-rules-v4','legacy'),default='user-rules-v5')
    p.add_argument('--execution',choices=('standard',),default='standard')
    p.add_argument('--model',default='gpt-6-luna')
    p.add_argument('--start-row',type=int,default=1);p.add_argument('--first',type=int,default=2000)
    p.add_argument('--workers',type=int,default=8);p.add_argument('--budget-usd',type=float,default=3)
    p.add_argument('--save-every',type=int,default=10)
    p.add_argument('--run',action='store_true');p.add_argument('--resume',action='store_true')
    a=p.parse_args(argv)
    if min(a.start_row,a.first,a.workers,a.budget_usd,a.save_every)<=0 or a.workers>16:raise CheckError('Giới hạn không hợp lệ')
    return run(a)

if __name__=='__main__':
    try:raise SystemExit(main())
    except (CheckError,OSError,ProviderFatal) as e:print('LỖI:',e);raise SystemExit(2)
