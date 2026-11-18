#!/usr/bin/env python3
"""Local image-URL grouping: selected records yes, other group members no; never delete rows."""
import argparse
from collections import Counter
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from approve_tool import ROOT, CheckError, read_csv, digest, atomic_json, export_csv
from matching import normalize


def timestamp():return datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%Y%m%d_%H%M%S_%f')


class GroupStore:
    def __init__(self,source,folder=None):
        self.source=Path(source).resolve()
        if self.source.is_relative_to(ROOT.parent/'done'):raise CheckError('Không chỉnh file trong done/')
        self.folder=Path(folder or ROOT/'outputs/image_groups'/self.source.stem)
        self.folder.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.session_backup=None;self.reload()

    def reload(self):
        self.raw=self.source.read_bytes();self.sha=digest(self.raw)
        self.rows,self.fields,_,self.encoding,self.newline,_=read_csv(self.source)
        self.groups={}
        for i,row in enumerate(self.rows):
            url=row['image_url']
            # Missing URLs are independent, never collapse all missing images together.
            gid=digest(('url:'+url if url.strip() else 'missing:'+str(i)).encode())
            self.groups.setdefault(gid,{'id':gid,'url':url,'indices':[]})['indices'].append(i)
        self.ordered=sorted(self.groups.values(),key=lambda g:(-len(g['indices']),g['indices'][0]))
        self.search={g['id']:normalize(g['url']+' '+' '.join(self.rows[i]['entity_name']+' '+
            self.rows[i].get('leaf_label','') for i in g['indices'])) for g in self.ordered}
        self.choices={};self.warning=''
        plan=self.folder/'selection.json'
        if plan.exists():
            saved=json.loads(plan.read_text())
            if saved.get('source_sha256')==self.sha:
                for gid,index in saved['choices'].items():
                    self.validate(gid,index);self.choices[gid]=index
            else:self.warning='CSV đã đổi: không áp dụng lựa chọn của phiên bản CSV cũ.'

    @staticmethod
    def selection_indices(value):
        return [] if value is None else [value] if type(value) is int else list(value)

    def validate(self,gid,index):
        if gid not in self.groups:raise CheckError('Nhóm ảnh không tồn tại')
        if index is None:return
        if type(index) is not int and not isinstance(index,list):raise CheckError('Lựa chọn phải là index hoặc danh sách index')
        values=self.selection_indices(index)
        if (any(type(i) is not int or i not in self.groups[gid]['indices'] for i in values)
                or len(values)!=len(set(values))):raise CheckError('Record giữ lại phải thuộc nhóm ảnh, không được lặp')

    def save_plan(self):
        atomic_json(self.folder/'selection.json',{'source':str(self.source),'source_sha256':self.sha,'choices':self.choices})

    def select(self,gid,index):
        with self.lock:
            self.validate(gid,index);self.choices[gid]=None if index==[] else index;self.save_plan();return self.stats()

    def auto(self):
        with self.lock:
            for g in self.ordered:
                if len(g['indices'])>1 and g['id'] not in self.choices:
                    rank={'yes':0,'':1,'no':2}
                    self.choices[g['id']]=min(g['indices'],key=lambda i:(rank.get(self.rows[i]['approve'],1),i))
            self.save_plan();return self.stats()

    def reset(self):
        with self.lock:self.choices={};self.save_plan();return self.stats()

    def is_reviewed(self,group):
        return all(self.rows[i]['approve'].strip().lower() in ('yes','no') for i in group['indices'])

    def stats(self):
        removed=sum(len(self.groups[g]['indices'])-len(self.selection_indices(i)) for g,i in self.choices.items() if i is not None)
        return {'file':self.source.name,'rows':len(self.rows),'unique_urls':len(self.groups),
                'duplicate_groups':sum(len(g['indices'])>1 for g in self.ordered),
                'excess_records':len(self.rows)-len(self.groups),'planned_removed':0,
                'planned_remaining':len(self.rows),
                'planned_yes':sum(len(self.selection_indices(i)) for i in self.choices.values()),
                'planned_no':removed,'reviewed_groups':sum(self.is_reviewed(g) for g in self.ordered),
                'selected_groups':len(self.choices),
                'approve_counts':dict(Counter(r['approve'] or 'blank' for r in self.rows)),
                'warning':self.warning}

    def page(self,q='',kind='duplicates',review='all',label='all',page=1,size=10,sort='most'):
        with self.lock:
            if sort not in ('most','fewest'):raise CheckError('Thứ tự sắp xếp không hợp lệ')
            q=normalize(q);found=[]
            for g in self.ordered:
                n=len(g['indices']);chosen=self.is_reviewed(g)
                if kind=='duplicates' and n<2:continue
                if kind=='unique' and n!=1:continue
                if review=='pending' and chosen:continue
                if review=='reviewed' and not chosen:continue
                if label!='all' and not any((self.rows[i]['approve'] or 'blank')==label for i in g['indices']):continue
                if q and q not in self.search[g['id']]:continue
                found.append(g)
            if sort=='fewest':found.sort(key=lambda g:(len(g['indices']),g['indices'][0]))
            pages=max(1,(len(found)+size-1)//size);page=max(1,min(page,pages))
            groups=[]
            for g in found[(page-1)*size:page*size]:
                groups.append({**g,'reviewed':self.is_reviewed(g),'has_selection':g['id'] in self.choices,'keep_index':self.selection_indices(self.choices.get(g['id']))[0] if self.selection_indices(self.choices.get(g['id'])) else None,
                    'keep_indices':self.selection_indices(self.choices.get(g['id'])),
                    'rows':[dict(self.rows[i],_index=i) for i in g['indices']]})
            return {'stats':self.stats(),'groups':groups,'matched':len(found),'page':page,'pages':pages}

    def labelled(self,group=None):
        changes={}
        for gid,index in self.choices.items():
            if group is not None and gid!=group:continue
            if index is not None:
                selected=set(self.selection_indices(index))
                for i in self.groups[gid]['indices']:changes[i]='yes' if i in selected else 'no'
        return [dict(r,approve=changes[i]) if i in changes else dict(r) for i,r in enumerate(self.rows)]

    def write(self,apply=False,group=None,all_no=False,all_yes=False):
        with self.lock:
            if all_no and all_yes:raise CheckError('Chỉ chọn một nhãn cho cả nhóm')
            if (all_no or all_yes) and (group is None or not apply):raise CheckError('Gán nhãn cả nhóm cần một nhóm cụ thể')
            if group is not None:
                self.validate(group,self.choices.get(group))
                if not (all_no or all_yes) and self.choices.get(group) is None:raise CheckError('Chọn ít nhất một record trong nhóm trước khi áp dụng')
                if not apply:raise CheckError('Group scope requires apply')
            if self.source.read_bytes()!=self.raw:raise CheckError('CSV đã đổi bên ngoài; khởi động lại server trước khi xuất/ghi')
            kept=self.labelled(group)
            if all_no or all_yes:
                indices=set(self.groups[group]['indices'])
                kept=[dict(r,approve='yes' if all_yes else 'no') if i in indices else dict(r) for i,r in enumerate(self.rows)]
            stamp=timestamp()
            changes=[{'row_index':i,'entity_id':a['entity_id'],'image_url':a['image_url'],
                      'before':a['approve'],'after':b['approve']}
                     for i,(a,b) in enumerate(zip(self.rows,kept)) if a['approve']!=b['approve']]
            report={'source':str(self.source),'source_sha256':self.sha,'before':len(self.rows),
                'removed':0,'remaining':len(kept),'changed_labels':len(changes),
                'group':group,'all_no':all_no,'all_yes':all_yes,'label_changes':changes,'applied':False}
            if group is None:
                target=self.folder/f'labelled_{stamp}.csv'
                export_csv(target,kept,self.fields,{},self.encoding,self.newline)
                actual,fields,*_=read_csv(target)
                if actual!=kept or fields!=self.fields:raise CheckError('Kiểm tra CSV xuất thất bại')
                report['export']=str(target)
            if apply and changes:
                if self.session_backup is None:
                    backupdir=ROOT/'backups';backupdir.mkdir(exist_ok=True)
                    backup=backupdir/f'{self.source.stem}_before_group_labels_{stamp}.csv'
                    with backup.open('xb') as f:f.write(self.raw)
                    self.session_backup=backup
                if self.source.read_bytes()!=self.raw:raise CheckError('CSV vừa đổi; không ghi đè')
                export_csv(self.source,kept,self.fields,{},self.encoding,self.newline)
                report.update(applied=True,backup=str(self.session_backup),backup_kind='session_initial')
                # Label-only edits preserve group indexes; keep other pending choices intact.
                self.rows=kept;self.raw=self.source.read_bytes();self.sha=digest(self.raw)
                self.warning=''
                if all_no:self.choices[group]=None
                if all_yes:self.choices[group]=list(self.groups[group]['indices'])
                self.save_plan()
            if all_no and not changes:
                self.choices[group]=None;self.save_plan()
            if all_yes and not changes:
                self.choices[group]=list(self.groups[group]['indices']);self.save_plan()
            atomic_json(self.folder/f'export_{stamp}.json',report)
            return report


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def send(self,code,data,kind='application/json; charset=utf-8'):
            data=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode()
            self.send_response(code);self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            u=urlparse(self.path)
            if u.path in ('/','/group_images.html'):
                return self.send(200,(ROOT/'group_images.html').read_bytes(),'text/html; charset=utf-8')
            if u.path!='/api/groups':return self.send(404,{'error':'Not found'})
            try:
                q={k:v[0] for k,v in parse_qs(u.query).items()}
                q['page']=int(q.get('page',1));q['size']=min(25,max(1,int(q.get('size',10))))
                self.send(200,store.page(**q))
            except (ValueError,TypeError,CheckError) as e:self.send(400,{'error':str(e)})
        def do_POST(self):
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc!=self.headers.get('Host'):return self.send(403,{'error':'Origin mismatch'})
            if 'application/json' not in self.headers.get('Content-Type',''):return self.send(415,{'error':'JSON required'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=10000:raise CheckError('Invalid request size')
                data=json.loads(self.rfile.read(size))
                routes={'/api/select':lambda:store.select(data['group'],data['keep_indices'] if 'keep_indices' in data else data['keep_index']),
                    '/api/auto':store.auto,'/api/reset':store.reset,
                    '/api/export':lambda:store.write(False),
                    '/api/apply-group':lambda:store.write(True,data['group']),
                    '/api/all-no':lambda:store.write(True,data['group'],all_no=True),
                    '/api/all-yes':lambda:store.write(True,data['group'],all_yes=True)}
                action=routes.get(urlparse(self.path).path)
                if action is None:return self.send(404,{'error':'Not found'})
                self.send(200,action())
            except (CheckError,ValueError,KeyError,TypeError,OSError) as e:self.send(400,{'error':str(e)})
        def log_message(self,*args):pass
    return Handler


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT.parent/'general_10m_part_02.csv')
    p.add_argument('--port',type=int,default=8010)
    p.add_argument('--state-dir',type=Path,help='Thư mục lưu lựa chọn/audit riêng cho phiên duyệt')
    a=p.parse_args();store=GroupStore(a.input,folder=a.state_dir)
    server=ThreadingHTTPServer(('127.0.0.1',a.port),make_handler(store))
    print(f'Mở http://127.0.0.1:{a.port} | {store.stats()}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
