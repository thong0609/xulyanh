#!/usr/bin/env python3
"""Offline comparison; treat check failures as pending, as the production wrapper does."""
import csv
import html
import json
from collections import Counter
from pathlib import Path
from approve_tool import ROOT, read_csv, atomic_json

def main():
    out=ROOT/'outputs/official_vs_shopaikey_latest100_20261118'
    parent=ROOT/'outputs/luna_shopaikey_cheap_remaining_all'
    selection=json.loads((out/'selection.json').read_text())
    old_all=[json.loads(l) for l in (parent/'results.jsonl').read_text().splitlines() if l.strip()]
    old={r['row_index']:r for r in old_all}
    new={r['row_index']:r for r in map(json.loads,(out/'results.jsonl').read_text().splitlines())}
    snapshot=read_csv(parent/'input_snapshot.csv')[0]
    bad_groups={snapshot[i]['image_url'] for i,r in new.items()
        if any(e['error']!='TARGET_IMAGE_CONTEXT_NOT_FOUND' for e in r.get('errors',[]))}
    comparisons=[];cards=[]
    esc=lambda s:html.escape(str(s),quote=True)
    for i in selection['sample_indices']:
        a=old[i];b=new.get(i,{});row=snapshot[i]
        errors=[e['error'] for e in b.get('errors',[]) if e['error']!='TARGET_IMAGE_CONTEXT_NOT_FOUND']
        pending=not b or row['image_url'] in bad_groups
        label='' if pending else b['approve']
        state='pending' if pending else 'same' if label==a['approve'] else 'different'
        oa=a.get('checks',{}).get('image_observation',{})
        ob=b.get('checks',{}).get('image_observation',{})
        sa=a.get('checks',{}).get('group_source',{});sb=b.get('checks',{}).get('group_source',{})
        c={'snapshot_data_row':i+1,'entity_name':a['entity_name'],'shop_label':a['approve'],
           'official_label':label,'comparison':state,'shop_reason':a['reason'],
           'official_reason':'DEFERRED_CHECK_ERROR' if pending else b['reason'],
           'official_errors':' | '.join(errors),'shop_ocr':' | '.join(oa.get('texts',[])),
           'official_ocr':' | '.join(ob.get('texts',[])),
           'shop_explanation':sa.get('explanation',''),'official_explanation':sb.get('explanation',''),
           'image_url':row['image_url'],'page_url':row['page_url']}
        comparisons.append(c)
        url=row['image_url'] if row['image_url'].startswith(('https://','http://')) else ''
        source=row['page_url'] if row['page_url'].startswith(('https://','http://')) else ''
        cards.append(f'<article data-state="{state}"><h2>Dòng snapshot {i+1}: {esc(a["entity_name"])}</h2>'
          f'<img loading="lazy" referrerpolicy="no-referrer" src="{esc(url)}"><a href="{esc(source)}" target="_blank" rel="noopener noreferrer">Mở nguồn</a>'
          f'<table><tr><th></th><th>ShopAIKey</th><th>OpenAI chính chủ</th></tr>'
          f'<tr><th>Nhãn</th><td>{esc(a["approve"])}</td><td>{esc(label or "trống · lỗi kiểm tra")}</td></tr>'
          f'<tr><th>Lý do</th><td>{esc(c["shop_reason"])}</td><td>{esc(c["official_reason"])} {esc(c["official_errors"])}</td></tr>'
          f'<tr><th>OCR</th><td>{esc(c["shop_ocr"])}</td><td>{esc(c["official_ocr"])}</td></tr>'
          f'<tr><th>Giải thích nguồn</th><td>{esc(c["shop_explanation"])}</td><td>{esc(c["official_explanation"])}</td></tr></table></article>')
    with (out/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(comparisons[0]));w.writeheader();w.writerows(comparisons)
    calls=json.loads((out/'usage.json').read_text())['calls']
    valid=[c for c in comparisons if c['comparison']!='pending']
    summary={'sample_records':len(comparisons),'image_groups':selection['image_groups'],
        'expanded_records':selection['expanded_records'],
        'shop_counts':dict(Counter(c['shop_label'] for c in comparisons)),
        'official_counts':dict(Counter(c['official_label'] or 'blank' for c in comparisons)),
        'comparison_counts':dict(Counter(c['comparison'] for c in comparisons)),
        'valid_pairs':len(valid),'valid_pair_label_changes':dict(Counter(c['shop_label']+' -> '+c['official_label'] for c in valid if c['comparison']=='different')),
        'api_requests':len(calls),'reported_input_tokens':sum(c['usage']['input_tokens'] for c in calls if 'usage' in c),
        'reported_output_tokens':sum(c['usage']['output_tokens'] for c in calls if 'usage' in c),
        'cost_usd_estimate_using_existing_config':sum(c['charged_or_reserved_usd'] for c in calls),
        'invalid_json_requests':1,
        'limits':['Historical ShopAIKey run versus one fresh official run; not a simultaneous provider benchmark.',
          'Full image groups retained; comparison restricted to the exact original 100 records.',
          'Model-source prompt receives text blocks and OCR stage is separate; source prompt does not receive the image.',
          'Production-style error filter applied offline: raw diagnostic pipeline NO labels caused by check errors are pending in comparison.csv.',
          'No manual ground-truth accuracy percentage; no main CSV/done/production labels changed.']}
    atomic_json(out/'comparison_summary.json',summary)
    original_summary=out/'summary.json'
    raw_summary=out/'pipeline_raw_summary.json'
    if original_summary.exists() and not raw_summary.exists():
        raw_summary.write_bytes(original_summary.read_bytes())
    atomic_json(original_summary,summary)
    doc='''<!doctype html><html lang="vi"><meta charset="utf-8"><title>Đối chứng OpenAI / ShopAIKey · 100 record</title>
<style>body{font:16px system-ui;background:#f3f5f7;color:#172d35;margin:24px}article{background:white;padding:20px;margin:20px 0;border-radius:10px}img{display:block;max-width:100%;height:230px;object-fit:contain;margin:15px 0}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{border:1px solid #ddd;padding:10px;vertical-align:top;overflow-wrap:anywhere}th:first-child{width:14%}h2{font-size:19px}select{font:inherit;padding:8px}[hidden]{display:none!important}</style>
<h1>Đối chứng cùng 100 record · gpt-6-luna</h1><p>Ảnh được tải khi mở trang. Nhãn lỗi kiểm tra được để trống. Đây là kết quả trước áp rule bí danh và duyệt tay.</p>'''
    doc+=f'<pre>{esc(json.dumps({k:summary[k] for k in ("shop_counts","official_counts","comparison_counts")},ensure_ascii=False,indent=2))}</pre>'
    doc+='<select id="filter"><option value="all">Tất cả</option><option value="different">Khác nhãn hợp lệ</option><option value="pending">Lỗi / chưa xử lý</option><option value="same">Cùng nhãn</option></select>'
    doc+=''.join(cards)+'''<script>document.getElementById('filter').onchange=function(){document.querySelectorAll('article').forEach(n=>n.hidden=this.value!=='all'&&n.dataset.state!==this.value)}</script></html>'''
    (out/'comparison.html').write_text(doc)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
