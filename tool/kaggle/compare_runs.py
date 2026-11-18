#!/usr/bin/env python3
"""Compare two completed GPU/API runs over identical rows; no inference is performed."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

TOOL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TOOL))
from approve_tool import CheckError, atomic_json, digest, read_csv


def load_run(folder):
    manifest=json.loads((folder/'manifest.json').read_text())
    rows={}
    for line in (folder/'results.jsonl').read_text().splitlines():
        value=json.loads(line);i=value['row_index']
        if i in rows:raise CheckError(f'Duplicate result row: {i}')
        rows[i]=value
    return manifest,rows


def compare(input_csv,left_dir,right_dir,output_dir,baseline_rows=False):
    source_rows,_,ids,_,_,sha=read_csv(input_csv)
    lm,left=load_run(left_dir);rm,right=load_run(right_dir)
    selected=lm.get('selected_indices')
    right_selected=rm.get('selected_indices')
    if (not isinstance(selected,list) or not isinstance(right_selected,list)
            or lm.get('input_sha256')!=sha or rm.get('input_sha256')!=sha):
        raise CheckError('Runs use different input snapshots or invalid selected rows')
    if baseline_rows:
        if rm.get('seed_indices')!=selected or not set(selected).issubset(right_selected):
            raise CheckError('Candidate phải lấy đúng seed của baseline và mở rộng nhóm ảnh')
    elif selected!=right_selected:
        raise CheckError('Runs use different input snapshots or selected rows')
    if set(left)!=set(selected) or set(right)!=set(right_selected):
        raise CheckError('Both runs must finish every selected row before comparison')
    for i,r in right.items():
        if type(i) is not int or not 0<=i<len(ids) or r.get('row_id')!=ids[i]:
            raise CheckError(f'Candidate row identity mismatch: {i}')
    output_dir.mkdir(parents=True,exist_ok=True);table=[]
    for n,i in enumerate(selected,1):
        a,b=left[i],right[i]
        if a.get('row_id')!=ids[i] or b.get('row_id')!=ids[i]:
            raise CheckError(f'Row identity mismatch: {i}')
        table.append({'sample_no':n,'row_index':i,'entity_id':source_rows[i]['entity_id'],
          'entity_name':source_rows[i]['entity_name'],'image_url':source_rows[i]['image_url'],
          'page_url':source_rows[i]['page_url'],'approve_v1':a['approve'],'approve_v2':b['approve'],
          'changed':'yes' if a['approve']!=b['approve'] else 'no',
          'reason_v1':a.get('reason',''),'reason_v2':b.get('reason',''),
          'relation_v2':b.get('checks',{}).get('page_match',{}).get('relation',''),
          'errors_v2':json.dumps(b.get('errors',[]),ensure_ascii=False)})
    path=output_dir/'comparison_openai_qwen_v2_2.csv'
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    summary={'input_sha256':sha,'selected':len(table),'candidate_selected':len(right_selected),'baseline_rows_only':baseline_rows,'openai_counts':dict(Counter(r['approve_v1'] or 'blank' for r in table)),
      'qwen_counts':dict(Counter(r['approve_v2'] or 'blank' for r in table)),
      'changed':sum(r['changed']=='yes' for r in table),
      'transitions':dict(Counter((r['approve_v1'] or 'blank')+' -> '+(r['approve_v2'] or 'blank') for r in table))}
    atomic_json(output_dir/'comparison_summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2));print(f'CSV: {path}')
    return path


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=TOOL/'input/general_10m_part_02_copy.csv')
    p.add_argument('--openai-dir',type=Path,default=TOOL/'outputs/pilot_v2_2')
    p.add_argument('--qwen-dir',type=Path,default=TOOL/'outputs/pilot_qwen_v2_2')
    p.add_argument('--output-dir',type=Path,default=TOOL/'outputs/qwen_compare_v2_2')
    a=p.parse_args();compare(a.input,a.openai_dir,a.qwen_dir,a.output_dir)
