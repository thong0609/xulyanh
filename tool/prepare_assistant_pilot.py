"""Prepare original pilot evidence without reading model answers or calling APIs."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageOps,ImageDraw
from approve_tool import ROOT,read_csv,atomic_json,export_csv,digest,encoded,HTTP_CACHE_VERSION,CheckError
from grouped_pipeline import image_groups
from run_grouped_luna_standard import StandardFetcher
p=ROOT/'outputs/assistant_direct_pilot50';p.mkdir(exist_ok=True)
source=ROOT/'input/general_10m_part_02_copy.csv'
rows,fields,ids,enc,nl,sha=read_csv(source)
b=json.loads((ROOT/'outputs/luna_v2_2_pilot50/manifest.json').read_text())
assert b['input_sha256']==sha
seed=b['selected_indices'];selected,groups=image_groups(rows,seed)
class Cached(StandardFetcher):
 def fetch(self,url,kind):
  k=digest(encoded([HTTP_CACHE_VERSION,url,kind]))
  if not (self.cache/(k+'.bin')).exists():raise CheckError('CACHE_UNAVAILABLE')
  return super().fetch(url,kind)
f=Cached(ROOT/'cache/http')
def prepare(pair):
 n,group=pair;first=rows[group[0]];entry={'group':n,'image_url':first['image_url'],'records':[{'row_index':i,'row_id':ids[i],'entity_name':rows[i]['entity_name'],'page_url':rows[i]['page_url']} for i in group],'sources':[]}
 try:(p/f'image_{n:02}.jpg').write_bytes(f.image(first['image_url']));entry['image_path']=str(p/f'image_{n:02}.jpg')
 except Exception as e:entry['image_error']=str(e)
 for url in dict.fromkeys(rows[i]['page_url'] for i in group):
  try:page=f.page(url,first['image_url']);entry['sources'].append({'url':url,'page':page})
  except Exception as e:entry['sources'].append({'url':url,'error':str(e)})
 return entry
with ThreadPoolExecutor(max_workers=8) as pool:entries=list(pool.map(prepare,enumerate(groups,1)))
atomic_json(p/'evidence.json',entries)
atomic_json(p/'manifest.json',{'source':str(source),'input_sha256':sha,'selected_indices':selected,'seed_indices':seed,'method':'assistant_direct_review','model_api_calls':0})
for start in range(0,len(entries),10):
 sheet=Image.new('RGB',(1500,5*230),'white');draw=ImageDraw.Draw(sheet)
 for k,e in enumerate(entries[start:start+10]):
  x=(k%2)*750;y=(k//2)*230
  draw.text((x+5,y+5),f'GROUP {e["group"]}',fill='black')
  ip=p/f'image_{e["group"]:02}.jpg'
  if ip.exists():
   im=Image.open(ip);im.thumbnail((730,200));sheet.paste(im,(x+5,y+25))
 sheet.save(p/f'sheet_{start//10+1}.jpg')
print(p,'groups',len(entries),'records',len(selected))
