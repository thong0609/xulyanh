#!/usr/bin/env python3
"""Propagate existing yes inside each image group only for compatible name/address variants."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime
from difflib import SequenceMatcher
import csv,json,re,os
from pathlib import Path
from zoneinfo import ZoneInfo
from approve_tool import ROOT,read_csv,export_csv,atomic_json,digest
from matching import profile_name,normalize,phrase_in
from address_rules import text_norm
from image_quality import protected_image_urls

GENERIC={'truong','mam','non','mau','giao','lop','duong','dai','lo','pho','cau','toa','nha','the',
 'trung','tam','thuong','mai','mall','center','tp','thanh','pho','tinh','quan','huyen','phuong','xa','thi','tran'}
CITIES=['ho chi minh','ha noi','da nang','hai phong','can tho','binh duong','dong nai','an giang','long an',
 'kien giang','tien giang','quang ninh','hai duong','thai binh','khanh hoa','gia lai','bac ninh','nghe an']

def canonical_text(name):
 n=text_norm(name)
 for old,new in [('hanoi','ha noi'),('hcmc','ho chi minh')]:
  n=re.sub(r'\b'+old+r'\b',new,n)
 return n

def family(name):
 n=normalize(name)
 for prefixes,kind in [
  (('truong mam non','mam non','truong mau giao','mau giao','lop mau giao'),'preschool'),
  (('truong tieu hoc',),'primary_school'),
  (('nha may xu ly nuoc thai',),'wastewater'),(('nha may nuoc',),'waterworks'),
  (('cau ',),'bridge'),(('duong ','dai lo '),'road'),
  (('khu do thi ','vinhomes '),'urban'),(('cong vien ',),'park')]:
  if any(n.startswith(x) for x in prefixes):return kind
 if 'mall' in n.split() or n.startswith(('vincom ','aeon ','trung tam thuong mai ')):return 'mall'
 if n.startswith(('toa nha ','the ')):return 'building'
 return ''

def identity(name):
 # Preserve numeric commas: Vành đai 3,5 must not become Vành đai 3.
 numeric_safe_name=re.sub(r'(?<=\d),(?=\d)', ' decimal ', name)
 core=canonical_text(profile_name(numeric_safe_name)['core_name'])
 # The city may precede an English mall name or follow it without parentheses.
 if family(name)=='mall':
  for city in CITIES:
   if core.startswith(city+' '):core=core[len(city):].strip()
   if core.endswith(' '+city):core=core[:-len(city)].strip()
 for prefix in ['toa nha ','the ','dai lo ','duong ','trung tam thuong mai ']:
  if core.startswith(prefix):core=core[len(prefix):]
 if family(name)=='mall':core=' '.join(w for w in core.split() if w not in ('mall','center','trung','tam','thuong','mai'))
 core=re.sub(r'\bso (?=\d)','',core)
 core=re.sub(r'(?<=\d) thang (?=\d)',' ',core)
 return ' '.join(core.split())

def location_phrases(rows):
 phrases=set()
 for row in rows:
  for part in re.split(r'\s+[-–—]\s+|[(),;]',row['entity_name'])[1:]:
   n=text_norm(part)
   n=re.sub(r'^(?:quan|phuong|huyen|xa|tp|thanh pho|tinh|thi tran)\s+','',n)
   if 2<=len(n.split())<=6 and not re.search(r'\b(?:school|preschool|kindergarten|montessori)\b',n):phrases.add(n)
 return phrases

def relation(a,b,places):
 fa,fb=family(a),family(b)
 if fa and fb and fa!=fb:return None
 # A combined street/entity name is not just a longer address for either member.
 slash_a=bool(re.search(r'(?<!\d)/(?!\d)',a.split('(')[0]))
 slash_b=bool(re.search(r'(?<!\d)/(?!\d)',b.split('(')[0]))
 if slash_a!=slash_b:return None
 ca,cb=identity(a),identity(b)
 if not ca or not cb:return None
 if re.findall(r'\d+',ca)!=re.findall(r'\d+',cb):return None
 if ca==cb:base=ca
 else:
  short,long=sorted((ca,cb),key=len)
  if phrase_in(short,long):
   # A brand-only mall name cannot identify a branch among several locations.
   if (fa=='mall' or fb=='mall') and len(short.split())==1:return None
   extra=(' '+long+' ').replace(' '+short+' ',' ',1).strip()
   if extra not in places and not re.fullmatch(r'(?:quan|phuong|huyen|xa)\s+\w+(?: \w+)*',extra):return None
   base=short
  elif SequenceMatcher(None,ca,cb).ratio()>=.94 and len(set(ca.split())&set(cb.split()))>=2:base=ca
  else:return None
 if len(base.replace(' ',''))<3:return None
 na,nb=canonical_text(a),canonical_text(b)
 if fa=='mall' or fb=='mall':
  na=re.sub(r'\bto hop\b','',na)
  nb=re.sub(r'\bto hop\b','',nb)
 for field in ['quan','phuong']:
  va=set(re.findall(r'\b'+field+r'\s+(\d+)\b',na));vb=set(re.findall(r'\b'+field+r'\s+(\d+)\b',nb))
  if va and vb and va.isdisjoint(vb):return None
 city_a={c for c in CITIES if phrase_in(c,na)};city_b={c for c in CITIES if phrase_in(c,nb)}
 if city_a and city_b and city_a.isdisjoint(city_b):return None
 # Compare address/detail tokens only after the shared name and common designators are removed.
 base_tokens=set(base.split())
 ta=set(na.split())-base_tokens-GENERIC;tb=set(nb.split())-base_tokens-GENERIC
 if ta==tb:return 'same_name_same_address'
 if ta<tb or tb<ta:return 'same_name_address_more_specific'
 if ta and tb and len(ta&tb)>=2 and len(ta&tb)/len(ta|tb)>=.85:return 'same_name_similar_address'
 return None

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--input',type=Path,default=ROOT/'outputs/luna_grouped_standard_v4_4000/selected_rows.csv')
 parser.add_argument('--apply',action='store_true');args=parser.parse_args()
 source=args.input.resolve()
 if not source.is_relative_to(ROOT/'outputs'):raise ValueError('Input phải nằm trong tool/outputs')
 raw=source.read_bytes();rows,fields,ids,enc,nl,sha=read_csv(source);assert digest(raw)==sha
 groups=defaultdict(list)
 for i,r in enumerate(rows):
  if r['image_url'].strip():groups[r['image_url']].append(i)
 places=location_phrases(rows);changes=[]
 blocked=protected_image_urls(source)
 for url,group in groups.items():
  if url in blocked:continue
  anchors=[i for i in group if rows[i]['approve'].strip().lower()=='yes']
  for i in group:
   if rows[i]['approve'].strip().lower()=='yes':continue
   for j in anchors:
    why=relation(rows[j]['entity_name'],rows[i]['entity_name'],places)
    if why:
     changes.append({'row_index':i,'data_row':i+1,'row_id':ids[i],'entity_name':rows[i]['entity_name'],
      'before':rows[i]['approve'],'after':'yes','anchor_data_row':j+1,'anchor_entity_name':rows[j]['entity_name'],
      'relation':why,'image_url':url});break
 stamp=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%Y%m%d_%H%M%S_%f')
 audit=source.parent/f'propagate_yes_{stamp}';audit.mkdir()
 if changes:
  with (audit/'changes.csv').open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(changes[0]));w.writeheader();w.writerows(changes)
 updated=[dict(r) for r in rows]
 for c in changes:updated[c['row_index']]['approve']='yes'
 report={'source':str(source),'applied':False,'source_sha_before':sha,'changes':len(changes),
  'groups_changed':len({c['image_url'] for c in changes}),'before_counts':dict(Counter(r['approve'] or 'blank' for r in rows)),
  'after_counts':dict(Counter(r['approve'] or 'blank' for r in updated)),
  'policy':'Direct original yes anchors only; same image, compatible name and address; no transitive chaining. Existing yes unchanged.'}
 if args.apply and changes:
  backup=source.parent/'backups'/f'selected_rows_before_propagate_yes_{stamp}.csv';backup.parent.mkdir(exist_ok=True)
  with backup.open('xb') as f:f.write(raw)
  if source.read_bytes()!=raw:raise RuntimeError('CSV changed externally; not written')
  export_csv(source,updated,fields,{},enc,nl)
  check,cf,*_=read_csv(source);assert check==updated and cf==fields
  changed={c['row_index'] for c in changes}
  assert all(check[i]==r for i,r in enumerate(rows) if i not in changed)
  report.update(applied=True,backup=str(backup),source_sha_after=digest(source.read_bytes()))
 atomic_json(audit/'report.json',report)
 print(json.dumps(report,ensure_ascii=False));print('audit',audit)

if __name__=='__main__':main()
