#!/usr/bin/env python3
"""Offline refinement of remaining missing-image-context cases; no model/network calls."""
import csv
import html
import json
import re
from collections import Counter
from urllib.parse import urljoin
from approve_tool import ROOT,HTTP_CACHE_VERSION,digest,encoded,atomic_json
from grouped_pipeline import page_key
from source_page import DOM,url_identity,image_urls
from classify_missing_image_contexts import variant_identity


def embedded_urls(value):
    # Decode URL escaping used in JSON/JS without executing JavaScript.
    text=html.unescape(value)
    text=re.sub(r'\\u([0-9a-fA-F]{4})',lambda m:chr(int(m[1],16)),text)
    text=text.replace('\\/','/')
    for match in re.finditer(r'''(?:https?:)?//[^\s"'<>`\\]+''',text):
        yield match.group(0)


def classify(url,target):
    key=digest(encoded([HTTP_CACHE_VERSION,url,'page']));folder=ROOT/'cache/http'
    raw_path=folder/(key+'.bin');meta_path=folder/(key+'.json')
    if not raw_path.exists() or not meta_path.exists():return {'category':'cache_missing','evidence_urls':[]}
    meta=json.loads(meta_path.read_text());raw=raw_path.read_bytes()
    try:text=raw.decode(meta.get('charset','utf-8'),errors='replace')
    except LookupError:text=raw.decode('utf-8',errors='replace')
    dom=DOM();dom.feed(text);base=meta['url'];exact=url_identity(target);variant=variant_identity(target)
    def matches(value):
        try:
            u=urljoin(base,value)
            return url_identity(u)==exact or variant_identity(u)==variant
        except ValueError:return False
    links=[];scripts=[];other_markup=[]
    for n in dom.root.walk():
        if n.tag=='a' and n.attrs.get('href') and matches(n.attrs['href']):
            links.append(urljoin(base,n.attrs['href']))
        if n.tag=='script':
            value=''.join(c for c in n.children if isinstance(c,str))
            scripts.extend(urljoin(base,u) for u in embedded_urls(value) if matches(u))
        elif n.tag in ('img','source'):
            other_markup.extend(u for u in image_urls(n,base) if matches(u))
        elif n.tag!='a':
            for value in n.attrs.values():
                if not isinstance(value,str):continue
                other_markup.extend(urljoin(base,u) for u in embedded_urls(value) if matches(u))
    if links:return {'category':'gallery_image_link','evidence_urls':list(dict.fromkeys(links)),
                     'also_in_script':bool(scripts)}
    if scripts and not other_markup:return {'category':'script_json_only','evidence_urls':list(dict.fromkeys(scripts))}
    return {'category':'other_unverified_context','evidence_urls':list(dict.fromkeys(other_markup)),
            'also_in_script':bool(scripts)}


def main():
    folder=ROOT/'outputs/luna_grouped_standard_unlabeled2000/blank_analysis'
    original=list(csv.DictReader((folder/'missing_context_450.csv').open(encoding='utf-8-sig')))
    remaining=[r for r in original if r['context_subcategory']=='other_unverified_context']
    assert len(remaining)==308
    memo={};output=[]
    for n,r in enumerate(remaining,1):
        key=(page_key(r['page_url']),r['image_url'])
        if key not in memo:memo[key]=classify(*key)
        d=memo[key]
        output.append({**r,'refined_category':d['category'],'refined_evidence_urls':json.dumps(d['evidence_urls'],ensure_ascii=False),
                       'also_in_script':d.get('also_in_script',d['category']=='script_json_only')})
        if n%75==0:print(f'{n}/{len(remaining)} classified',flush=True)
    with (folder/'gallery_script_remaining_308.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
    summary={'records':len(output),'categories':dict(Counter(r['refined_category'] for r in output)),
             'rules':{'gallery_image_link':'yes','script_json_only':'no'},
             'note':'Previously approved empty-context/metadata/variant records excluded. Links take priority over scripts. Unknowns unchanged.'}
    atomic_json(folder/'gallery_script_remaining_308_summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
