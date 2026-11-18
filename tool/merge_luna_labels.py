#!/usr/bin/env python3
"""Merge completed Luna labels by full record identity, with backup and audit."""
import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
from approve_tool import ROOT, CheckError, read_csv, digest, atomic_json, export_csv


def merge(source,run_dir,apply=False):
    source=Path(source).resolve();run_dir=Path(run_dir)
    if source.is_relative_to(ROOT.parent/'done'):raise CheckError('Không chỉnh file trong done/')
    raw=source.read_bytes()
    rows,fields,_,enc,newline,_=read_csv(source)
    manifest=json.loads((run_dir/'manifest.json').read_text())
    snapshot=ROOT/'input/general_10m_part_02_copy.csv'
    original,_,ids,_,_,sha=read_csv(snapshot)
    if sha!=manifest['input_sha256']:raise CheckError('Luna input snapshot mismatch')
    results={}
    for line in (run_dir/'results.jsonl').read_text().splitlines():
        r=json.loads(line);i=r['row_index']
        if i in results or i not in manifest['selected_indices'] or r['row_id']!=ids[i]:
            raise CheckError('Luna record identity mismatch')
        if r['approve'] not in ('yes','no',''):raise CheckError('Invalid Luna label')
        results[i]=r
    if set(results)!=set(manifest['selected_indices']):raise CheckError('Luna run not complete')
    # Include every data field except approve, never match entity_id alone.
    key=lambda r:tuple(r[k] for k in fields if k!='approve')
    lookup={};counts=Counter();updates=[]
    for n,r in enumerate(rows):lookup.setdefault(key(r),[]).append(n)
    for i,r in results.items():
        matches=lookup.get(key(original[i]),[])
        if not matches:counts['previously_removed']+=1;continue
        if len(matches)!=1:raise CheckError('Ambiguous duplicate record; inspect before merging')
        n=matches[0];counts['matched']+=1
        if not r['approve']:counts['luna_blank']+=1;continue
        old=rows[n]['approve']
        if old and old!=r['approve']:raise CheckError('Existing label conflicts with Luna')
        if old==r['approve']:counts['already_same']+=1;continue
        updates.append({'main_row_index':n,'original_row_index':i,'row_id':r['row_id'],
                        'old_approve':old,'approve':r['approve']})
        rows[n]['approve']=r['approve'];counts['updated_'+r['approve']]+=1
    report={'source':str(source),'run':str(run_dir),'counts':dict(counts),'rows':len(rows),
            'labels_after':dict(Counter(r['approve'] or 'blank' for r in rows)),
            'source_sha256_before':digest(raw),'applied':False}
    if apply and updates:
        folder=ROOT/'backups';folder.mkdir(exist_ok=True)
        stamp=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%Y%m%d_%H%M%S_%f')
        backup=folder/f'{source.stem}_before_luna_merge_{stamp}.csv'
        with backup.open('xb') as f:f.write(raw)
        if source.read_bytes()!=raw:raise CheckError('Source changed during merge')
        export_csv(source,rows,fields,{},enc,newline)
        actual,af,*_=read_csv(source)
        if actual!=rows or af!=fields:raise CheckError('CSV verification failed; restore backup')
        report.update(applied=True,backup=str(backup),source_sha256_after=digest(source.read_bytes()),updates=updates)
        path=folder/f'luna_merge_{stamp}.json';atomic_json(path,report)
        report['audit']=str(path)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT.parent/'general_10m_part_02.csv')
    p.add_argument('--run-dir',type=Path,default=ROOT/'outputs/luna_rows_2001_4000')
    p.add_argument('--apply',action='store_true')
    a=p.parse_args();r=merge(a.input,a.run_dir,a.apply)
    print(json.dumps({k:v for k,v in r.items() if k!='updates'},ensure_ascii=False,indent=2))
