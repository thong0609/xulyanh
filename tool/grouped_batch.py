"""Replay grouped decisions against durable Batch answers, bounded remote batches; per-group dependencies remain sequential."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import os
import threading
import time
from approve_tool import CheckError,atomic_json,export_csv
from api_economy import StopBudget
from api_providers import ProviderFatal
from batch_api import BatchStore,BatchModelClient,NeedsBatch,OpenAIBatchAPI
from grouped_pipeline import GroupPipeline


class ReplayFetcher:
    """Successes use the underlying disk cache; avoid repeating failed HTTP in a replay."""
    def __init__(self,base):self.base=base;self.errors={};self.lock=threading.RLock()
    def call(self,method,*args):
        key=(method,)+args
        with self.lock:
            if key in self.errors:raise CheckError(self.errors[key])
        try:return getattr(self.base,method)(*args)
        except CheckError as error:
            with self.lock:self.errors[key]=str(error)
            raise
    def image(self,url):return self.call('image',url)
    def page(self,*args):return self.call('page',*args)


def run_batches(args,output,rows,fields,ids,enc,newline,seed,selected,groups,overrides,key,rates,
                fetcher_factory,api_factory=OpenAIBatchAPI):
    from approve_tool import ROOT
    batch_rates=(rates[0]*.5*(1.25 if args.model=='gpt-6-luna' else 1),rates[1]*.5)
    store=BatchStore(output/'batch',args.model,args.budget_usd,*batch_rates)
    client=BatchModelClient(store)
    engine_class=GroupPipeline
    if getattr(args,'policy','legacy')=='user-rules-v4':
        from grouped_user_rules import UserRulesGroupPipeline
        engine_class=UserRulesGroupPipeline
    engine_options={'require_ocr_response':True}
    if getattr(args,'policy','legacy')=='user-rules-v4':engine_options['one_yes_per_image']=getattr(args,'group_yes','multiple')=='single'
    engine=engine_class(client,ReplayFetcher(fetcher_factory(ROOT/'cache/http')),overrides,**engine_options)
    api=api_factory(key)
    results={};journal_path=output/'results.jsonl';selected_set=set(selected)
    if journal_path.exists():
        data=journal_path.read_bytes()
        if data and not data.endswith(b'\n'):
            data=data[:data.rfind(b'\n')+1];journal_path.write_bytes(data)
        for line in data.splitlines():
            r=json.loads(line);i=r['row_index']
            if i not in selected_set or r['row_id']!=ids[i] or i in results:raise CheckError('Journal identity mismatch')
            results[i]=r
    initial=len(results);started=time.monotonic();stop=None;finished=0
    max_active=getattr(args,'max_active_batches',1)
    waiting={};budget_blocked=set();wake_budget=True
    def save():
        export_csv(output/'reviewed.csv',rows,fields,results,enc,newline)
        export_csv(output/'selected_rows.csv',[rows[i] for i in selected],fields,
                   {n:results[i] for n,i in enumerate(selected) if i in results},enc,newline)
        atomic_json(output/'summary.json',{'selected':len(selected),'seed_rows':len(seed),
            'completed':len(results),'remaining':len(selected)-len(results),'complete':len(results)==len(selected),
            'image_groups':len(groups),'max_active_batches':max_active,'counts':dict(Counter(r['approve'] or 'blank' for r in results.values())),
            'stop_reason':stop,'processed_this_session':len(results)-initial,
            'elapsed_seconds_this_session':round(time.monotonic()-started,2),**store.report()})
    def process(group):
        items=[(i,dict(rows[i],approve=results[i]['approve']) if i in results else rows[i],ids[i]) for i in group]
        return engine.process_group(items)
    try:
        with journal_path.open('a',encoding='utf-8') as journal:
            while len(results)<len(selected):
                pending=[]
                for g in groups:
                    if all(i in results for i in g):continue
                    group_key=tuple(g)
                    if group_key in waiting:
                        if not (store.folder/(waiting[group_key]+'.answer.json')).exists():continue
                        del waiting[group_key]
                    if group_key in budget_blocked and not wake_budget:continue
                    budget_blocked.discard(group_key);pending.append(g)
                wake_budget=False
                # Bounded worker count, no synchronous model requests in these workers.
                with ThreadPoolExecutor(max_workers=args.workers) as pool:
                    futures={pool.submit(process,g):g for g in pending}
                    for future in as_completed(futures):
                        group=futures[future]
                        try:answers=future.result()
                        except NeedsBatch as error:
                            task_key=str(error)
                            if task_key not in store.state['requests']:raise CheckError('BATCH_WAIT_KEY_INVALID')
                            waiting[tuple(group)]=task_key;continue
                        except StopBudget:
                            budget_blocked.add(tuple(group));continue
                        if {r['row_index'] for r in answers}!=set(group):raise CheckError('GROUP_RESULT_MISMATCH')
                        fresh=[r for r in answers if r['row_index'] not in results]
                        journal.write(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in fresh))
                        journal.flush();os.fsync(journal.fileno())
                        for r in fresh:results[r['row_index']]=r
                        finished+=1
                        if finished%args.save_every==0:save()
                save()
                if len(results)==len(selected):break
                ingested=False
                # Poll/reconcile EVERY existing job first. No new creates if reconciliation fails.
                active=[j for j in store.state['jobs'] if j['status']!='ingested']
                for job in active:
                    if store.submit_or_poll(job,api):ingested=True
                # Uploads/create calls are serialized locally, but all submitted jobs remain
                # active together on OpenAI. Requests cannot enter two jobs.
                while sum(j['status']!='ingested' for j in store.state['jobs'])<max_active:
                    job=store.prepare(args.batch_requests,int(args.batch_mb*1024**2),allow_multiple=True)
                    if job is None:break
                    print(f"Submit batch {job['job']} | {len(job['keys'])} requests",flush=True)
                    if store.submit_or_poll(job,api):ingested=True
                active=[j for j in store.state['jobs'] if j['status']!='ingested']
                report=store.report()
                print(f"{len(results)}/{len(selected)} records | active batches {len(active)}/{max_active} | "
                      f"queued source={report['queued_source_requests']}, OCR={report['queued_ocr_requests']} | "
                      f"reported=${report['reported_cost_usd']:.4f}, reserved=${report['reserved_cost_usd']:.4f}",flush=True)
                if ingested:
                    # Only groups whose own answer arrived can progress. Other batches keep running.
                    wake_budget=True;stop=None;save();continue
                if not active:
                    stop='BUDGET_LIMIT' if budget_blocked else 'NO_PROGRESS';break
                stop='WAITING_BATCH';save()
                for job in active:print(f"{job.get('batch_id') or job['job']} | {job['status']} | {len(job['keys'])} requests",flush=True)
                if not args.watch:return 0
                time.sleep(args.poll_seconds)
    except KeyboardInterrupt:stop='INTERRUPTED: batch đã gửi vẫn chạy; dùng --resume'
    except (ProviderFatal,CheckError,OSError,ValueError,KeyError) as error:stop=str(error)
    finally:save()
    print('Output:',output,flush=True)
    return 2 if stop else 0
