#!/usr/bin/env python3
"""User override: remaining blank records on top-school-list URLs no; other blanks yes."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
from urllib.parse import unquote,urlsplit
from zoneinfo import ZoneInfo
from approve_tool import ROOT,read_csv,export_csv,atomic_json,digest


def top_school_url(url):
    # Match the page path, not a domain containing 'top' or an ordinary news article with a number.
    path=unquote(urlsplit(url).path).lower()
    school=bool(re.search(r'(?:truong|school|preschool|kindergarten)',path))
    if not school:return False
    top=bool(re.search(r'(?:^|[/_-])top(?:[-_/]|\d)',path)
             or re.search(r'/(?:toplist|top-list|topaz)(?:/|$)',path))
    ranked_list=bool(re.search(r'danh[-_]sach[-_]\d+',path)
                     and re.search(r'hang[-_]dau|tot[-_]nhat|chat[-_]luong|xuat[-_]sac',path))
    return top or ranked_list


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    folder=ROOT/'outputs/luna_grouped_standard_unlabeled2000';source=folder/'selected_rows.csv'
    raw=source.read_bytes();rows,fields,ids,enc,newline,sha=read_csv(source)
    if digest(raw)!=sha:raise RuntimeError('CSV changed while reading; rerun')
    updated=[dict(r) for r in rows];changes=[]
    for i,row in enumerate(rows):
        if row['approve'].strip():continue
        is_top=top_school_url(row['page_url']);label='no' if is_top else 'yes'
        updated[i]['approve']=label
        changes.append({'selected_csv_row_index':i,'row_id':ids[i],'entity_id':row['entity_id'],
            'entity_name':row['entity_name'],'page_url':row['page_url'],'before':row['approve'],
            'after':label,'reason':'TOP_SCHOOL_LIST_URL' if is_top else 'OTHER_SOURCE_URL'})
    stamp=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%Y%m%d_%H%M%S_%f')
    report={'source':str(source),'applied':False,'source_sha_before':sha,'target_records':len(changes),
            'before_counts':dict(Counter(r['approve'] or 'blank' for r in rows)),
            'target_labels':dict(Counter(c['after'] for c in changes)),
            'after_counts':dict(Counter(r['approve'] or 'blank' for r in updated)),
            'instruction':'Only currently blank records: top/ranked school-list URLs no, remaining URLs yes; preserve already labelled records.',
            'changes':changes}
    if args.apply and changes:
        backup=folder/'backups'/f'selected_rows_before_remaining_url_override_{stamp}.csv';backup.parent.mkdir(exist_ok=True)
        with backup.open('xb') as f:f.write(raw)
        if source.read_bytes()!=raw:raise RuntimeError('CSV changed externally; not written')
        export_csv(source,updated,fields,{},enc,newline)
        actual,actual_fields,*_=read_csv(source)
        assert actual==updated and actual_fields==fields and len(actual)==len(rows)
        assert all(actual[i]==r for i,r in enumerate(rows) if r['approve'].strip())
        report.update(applied=True,backup=str(backup),source_sha_after=digest(source.read_bytes()))
        atomic_json(folder/f'manual_override_remaining_urls_{stamp}.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='changes'},ensure_ascii=False,indent=2))
    for c in changes:
        if c['after']=='no':print('NO:',c['page_url'])

if __name__=='__main__':main()
