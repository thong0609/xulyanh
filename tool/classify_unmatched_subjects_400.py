#!/usr/bin/env python3
"""Prepare auditable proposals for the user's name/branch overrides; no API or label writes."""
import csv,json,re
from collections import Counter
from approve_tool import ROOT,atomic_json
from matching import profile_name,normalize

GENERIC_SUBJECTS={normalize(s) for s in [
 'Cơ sở 2','Hệ thống cơ sở','Hà Nội: Rộn ràng ngày hội đến trường tại phường Hà Đông, Thanh Liệt, Kiến Hưng',
 'Trường mầm non công lập lớn nhất TP.Thủ Đức, TP.HCM','Trường mầm non công lập rộng 7.500 m2 tại quận 7, TP.HCM',
 'Trường mầm non ở Biên Hòa','Tân Kỳ (Nghệ An)','ngôi trường mầm non','nhóm, lớp mầm non độc lập',
 'trường Mầm non công lập','trường mầm non quốc tế','trẻ em mầm non','Mùa xuân và Hoa Mai']}
DESCRIPTORS={'truong','mam','non','mau','giao','lop','he','thong','duc','lien','cap','quoc','te','song','ngu','tu','thuc','doc','lap',
 'cong','school','schools','preschool','kindergarten','academy','international','bilingual','montessori','clc','steam','stem'}
# Phrase removal avoids deleting meaningful syllables inside proper names.
PREFIXES=['he thong giao duc','he thong','giao duc','truong mam non','lop mam non doc lap','lop mau giao',
          'truong mau giao','mam non','mau giao','truong','lop','quoc te','song ngu','tu thuc','cong lap','lien cap',
          'can thiep tu ky','hoa nhap','montessori','clc']

def names(value):
 p=profile_name(value)
 result=[]
 for name in [p['core_name']]+p.get('possible_aliases',[]):
  while True:
   prefix=next((x for x in PREFIXES if name.startswith(x+' ')),None)
   if prefix is None:break
   name=name[len(prefix)+1:]
  name=re.sub(r'\b(?:cs\s*\d+|co so\s*\d+)\b',' ',name)
  name=re.sub(r'\b(?:school|schools|preschool|kindergarten|academy|international|bilingual|montessori)\b',' ',name)
  name=' '.join(name.split())
  if any(c.isalpha() for c in name) and not re.fullmatch(r'(?:so )?\d+(?: \d+)*',name):
   name=re.sub(r'\s+(?:\d+|i|ii|iii)$','',name)
  if name:result.append(name)
 return result

def same_name(a,b):
 for left in names(a):
  for right in names(b):
   short,long=sorted((left,right),key=len)
   if short==long:return short
   if ' '+short+' ' in ' '+long+' ':
    useful=[w for w in short.split() if w not in DESCRIPTORS and not w.isdigit()]
    if len(useful)>=2 or len(useful)==1 and len(useful[0])>=5:return short
 return ''

def main():
 folder=ROOT/'outputs/luna_grouped_standard_unlabeled2000/blank_analysis'
 wanted={int(r['row_index']) for r in csv.DictReader((folder/'records.csv').open(encoding='utf-8-sig')) if r['category']=='no_winner_unmatched_subject'}
 records=[json.loads(x) for x in (folder.parent/'results.jsonl').read_text().splitlines()];records=[r for r in records if r['row_index'] in wanted]
 pairs={};out=[]
 for r in records:
  d=r['checks']['group_source'];key=(r['entity_name'],d['observed_name'])
  if key not in pairs:pairs[key]=len(pairs)
  match=same_name(*key)
  kind='generic_description' if normalize(key[1]) in GENERIC_SUBJECTS else 'shared_name_or_system' if match else 'different_name'
  out.append({'pair_no':pairs[key],'row_index':r['row_index'],'row_id':r['row_id'],'entity_name':key[0],
    'observed_name':key[1],'model_explanation':d['explanation'],'category':kind,
    'new_approve':'no' if kind=='different_name' else 'yes','matched_base':match})
 atomic_json(folder/'unmatched_subjects_400_proposals.json',out)
 print('proposals',Counter(r['category'] for r in out))
 for pair,n in pairs.items():
  r=next(x for x in out if x['pair_no']==n)
  print(f"{n:03} {r['new_approve']:3} | {pair[0]} | {pair[1]}")

if __name__=='__main__':main()
