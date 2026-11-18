#!/usr/bin/env python3
"""Offline audit of saved blank decisions; does not alter labels or call APIs."""
import argparse
from collections import Counter,defaultdict
import csv
import json
from pathlib import Path
from approve_tool import ROOT,read_csv,evidence_present,atomic_json
from grouped_pipeline import common_brand
from matching import profile_name,exact_match

LABELS={
 'image_error':'Lỗi ảnh hoặc response OCR',
 'source_image_context_missing':'Không trích được ngữ cảnh của ảnh trong nguồn',
 'source_extraction_incomplete':'Nguồn bị trích xuất thiếu hoặc bị chặn',
 'source_other_error':'Lỗi nguồn hoặc response kiểm nguồn khác',
 'winner_evidence_invalid':'Model chọn ứng viên nhưng bằng chứng tên chưa hợp lệ',
 'winner_name_not_verified':'Model chọn ứng viên nhưng rule tên không xác minh được',
 'winner_other_guard':'Model chọn ứng viên nhưng chưa được chốt bởi guard khác',
 'no_winner_no_verified_subject':'Model không chọn ứng viên và không dẫn đủ bằng chứng tên',
 'no_winner_name_rule_hit':'Model không chọn ứng viên dù tên quan sát qua được rule tên',
 'no_winner_unmatched_subject':'Model không chọn ứng viên; tên trong nguồn chưa khớp theo rule',
}

def analyze(folder):
    rows,_,ids,_,_,sha=read_csv(folder/'input_snapshot.csv')
    manifest=json.loads((folder/'manifest.json').read_text())
    assert sha==manifest['input_sha256']
    results=[json.loads(line) for line in (folder/'results.jsonl').read_text().splitlines()]
    assert len({r['row_index'] for r in results})==len(results)
    assert all(ids[r['row_index']]==r['row_id'] for r in results)
    groups=defaultdict(list)
    for i in manifest['selected_indices']:
        groups[rows[i]['image_url'] or f'missing:{i}'].append(i)
    overrides=json.loads((ROOT/'name_overrides.json').read_text())
    profiles={ids[i]:profile_name(rows[i]['entity_name'],overrides.get(rows[i]['entity_id'])) for i in manifest['selected_indices']}
    audit=[]
    for r in results:
        if r['approve']:continue
        i=r['row_index'];group=groups[rows[i]['image_url'] or f'missing:{i}']
        brand=common_brand([profiles[ids[j]] for j in group])
        def hit(rid,subject):
            p=profiles[rid]
            return bool(exact_match(p,subject) or brand and p['scope']!='group' and exact_match(profile_name(brand),subject))
        d=r.get('checks',{}).get('group_source',{});errors=r.get('errors',[])
        subject=d.get('observed_name','');winner=d.get('winner_id','');blocks=d.get('evidence_blocks',[])
        valid=bool(subject.strip() and blocks and evidence_present(subject,[b['text'] for b in blocks]))
        name_hit=hit(winner,subject) if winner in profiles else False
        any_hit=bool(subject.strip()) and any(hit(ids[j],subject) for j in group if rows[j]['approve']!='no')
        if any(e['step']=='image' for e in errors):category='image_error'
        elif errors:
            codes={e['error'] for e in errors}
            if 'TARGET_IMAGE_CONTEXT_NOT_FOUND' in codes:category='source_image_context_missing'
            elif 'PAGE_EXTRACTION_INCOMPLETE' in codes:category='source_extraction_incomplete'
            else:category='source_other_error'
        elif winner:
            category='winner_evidence_invalid' if not valid else 'winner_name_not_verified' if not name_hit else 'winner_other_guard'
        else:
            category='no_winner_no_verified_subject' if not valid else 'no_winner_name_rule_hit' if any_hit else 'no_winner_unmatched_subject'
        audit.append({'row_index':i,'data_row':i+1,'row_id':r['row_id'],'entity_name':r['entity_name'],
            'image_url':rows[i]['image_url'],'page_url':rows[i]['page_url'],
            'category':category,'category_vi':LABELS[category],
            'observed_name':subject,'proposed_winner_id':winner,'verified_subject':valid,'winner_name_rule_hit':name_hit,
            'model_explanation':d.get('explanation',''),'errors':json.dumps(errors,ensure_ascii=False)})
    counts=Counter(a['category'] for a in audit)
    errors=Counter(e['step']+': '+e['error'] for r in results if not r['approve'] for e in r.get('errors',[]))
    summary={'saved_records':len(results),'counts':dict(Counter(r['approve'] or 'blank' for r in results)),
        'blank_records':len(audit),'categories':{k:{'description':LABELS[k],'records':n} for k,n in counts.items()},
        'error_occurrences_may_overlap':dict(errors),
        'note':'Categories are mutually exclusive; source decision is only the LAST logged source response, not a replay of all sources. Rule mismatch does not prove a real entity mismatch. Recomputed using current matching rules and original snapshot.'}
    out=folder/'blank_analysis';out.mkdir(exist_ok=True)
    atomic_json(out/'summary.json',summary)
    with (out/'records.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(audit[0]));writer.writeheader();writer.writerows(audit)
    assert sum(counts.values())==len(audit)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    for k in counts:
        print('\nEXAMPLE',k)
        for a in [a for a in audit if a['category']==k][:2]:
            print(json.dumps({n:a[n] for n in ['data_row','entity_name','observed_name','model_explanation','errors']},ensure_ascii=False))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-dir',type=Path,default=ROOT/'outputs/luna_grouped_standard_unlabeled2000')
    analyze(p.parse_args().run_dir.resolve())
