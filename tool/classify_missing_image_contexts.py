#!/usr/bin/env python3
"""Classify original missing-context records using cached HTML only; no network or labels changed."""
import csv
import json
from collections import Counter
from pathlib import Path
import re
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode,urljoin
from approve_tool import ROOT,HTTP_CACHE_VERSION,digest,encoded,evidence_blocks,atomic_json
from grouped_pipeline import page_key
from source_page import DOM,extract_page,image_urls,url_identity

RESIZE_PARAMS={'w','h','width','height','q','quality','fit','crop','format','auto','resize','dpr'}


def variant_identity(url):
    p=urlsplit(url_identity(url))
    path=re.sub(r'/+','/',p.path)
    path=re.sub(r'/(?:zoom|resize)/\d+(?:[_x]\d+)?/','/',path)
    path=re.sub(r'/thumb_w/\d+/','/',path)
    query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
           if k.lower() not in RESIZE_PARAMS and not k.lower().startswith('utm_')]
    return urlunsplit((p.scheme,p.netloc,path,urlencode(sorted(query)),''))


def metadata_urls(dom,base):
    def image_value(value):
        if isinstance(value,str):yield urljoin(base,value)
        elif isinstance(value,list):
            for x in value:yield from image_value(x)
        elif isinstance(value,dict):
            for k in ('url','contentUrl','thumbnailUrl'):
                if k in value:yield from image_value(value[k])
    def walk(value):
        if isinstance(value,dict):
            types=value.get('@type',[]);types=[types] if isinstance(types,str) else types
            if 'ImageObject' in types:
                yield from image_value(value)
            for k,v in value.items():
                if k in ('image','thumbnailUrl','primaryImageOfPage'):yield from image_value(v)
                elif isinstance(v,(dict,list)):yield from walk(v)
        elif isinstance(value,list):
            for x in value:yield from walk(x)
    for n in dom.root.walk():
        if n.tag=='meta':
            key=(n.attrs.get('property') or n.attrs.get('name') or n.attrs.get('itemprop') or '').lower()
            if key in ('og:image','og:image:url','og:image:secure_url','twitter:image','twitter:image:src','image','thumbnailurl'):
                value=n.attrs.get('content','')
                if value:yield urljoin(base,value)
        elif n.tag=='link' and 'image_src' in (n.attrs.get('rel') or '').lower().split():
            if n.attrs.get('href'):yield urljoin(base,n.attrs['href'])
        elif n.tag=='script' and (n.attrs.get('type') or '').lower()=='application/ld+json':
            try:value=json.loads(''.join(x for x in n.children if isinstance(x,str)))
            except (ValueError,TypeError):continue
            yield from walk(value)


def classify(url,target):
    key=digest(encoded([HTTP_CACHE_VERSION,url,'page']));folder=ROOT/'cache/http'
    data_path=folder/(key+'.bin');meta_path=folder/(key+'.json')
    if not data_path.exists() or not meta_path.exists():return {'category':'cache_missing','evidence_urls':[]}
    meta=json.loads(meta_path.read_text());raw=data_path.read_bytes()
    try:text=raw.decode(meta.get('charset','utf-8'),errors='replace')
    except LookupError:text=raw.decode('utf-8',errors='replace')
    page=extract_page(text,meta['url'],target)
    blocks=[]
    for i,c in enumerate(page['contexts']):
        for field in ('headings','alt','local_text'):
            values=c.get(field,[])[-1:] if field=='headings' else [c.get(field,'')]
            for j,value in enumerate(values):blocks.extend(evidence_blocks(value,f'c{i}_{field}_{j}',i,field))
    if page['incomplete']:return {'category':'cached_page_incomplete','evidence_urls':[]}
    if page['target_found'] and not blocks:
        return {'category':'image_found_empty_context','evidence_urls':[c['matched_url'] for c in page['contexts']]}
    dom=DOM();dom.feed(text);target_id=url_identity(target);variant=variant_identity(target)
    matches_meta=[u for u in metadata_urls(dom,meta['url']) if url_identity(u)==target_id or variant_identity(u)==variant]
    if matches_meta:return {'category':'image_metadata_match','evidence_urls':list(dict.fromkeys(matches_meta))}
    matches_variant=[u for n in dom.root.walk() if n.tag in ('img','source') for u in image_urls(n,meta['url'])
                     if url_identity(u)!=target_id and variant_identity(u)==variant]
    if matches_variant:return {'category':'image_url_variant','evidence_urls':list(dict.fromkeys(matches_variant))}
    if blocks:return {'category':'cached_extraction_now_has_text','evidence_urls':[]}
    return {'category':'other_unverified_context','evidence_urls':[]}


def main():
    folder=ROOT/'outputs/luna_grouped_standard_unlabeled2000/blank_analysis'
    records=[r for r in csv.DictReader((folder/'records.csv').open(encoding='utf-8-sig')) if r['category']=='source_image_context_missing']
    memo={};output=[]
    for n,r in enumerate(records,1):
        pair=(page_key(r['page_url']),r['image_url'])
        if pair not in memo:memo[pair]=classify(*pair)
        d=memo[pair]
        output.append({**r,'context_subcategory':d['category'],'evidence_urls':json.dumps(d['evidence_urls'],ensure_ascii=False)})
        if n%75==0:print(f'{n}/{len(records)} classified',flush=True)
    with (folder/'missing_context_450.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
    summary={'records':len(output),'categories':dict(Counter(r['context_subcategory'] for r in output)),
        'source':'Cached HTML only; exact/controlled resize variants and image metadata. Arbitrary JavaScript data and gallery links alone excluded.',
        'approved_categories':['image_found_empty_context','image_metadata_match','image_url_variant']}
    atomic_json(folder/'missing_context_450_summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
