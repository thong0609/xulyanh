#!/usr/bin/env python3
"""Build a standalone comparison viewer next to its CSV; no API or network calls."""
import argparse
import base64
import csv
import hashlib
import html
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


def preview(url):
    # Same raw cache keys as the pilot. Embed thumbnails for file:// viewing offline.
    for version in ('pilot-v1', 'pilot-v2'):
        key = hashlib.sha256(json.dumps([version, url, 'image'], ensure_ascii=False,
                                       sort_keys=True).encode()).hexdigest()
        p = ROOT/'cache/http'/(key+'.bin')
        if p.is_file():
            try:
                from PIL import Image, ImageOps
                with Image.open(p) as im:
                    im = ImageOps.exif_transpose(im).convert('RGB')
                    im.thumbnail((900, 650))
                    output = io.BytesIO(); im.save(output, format='JPEG', quality=83)
                    return 'data:image/jpeg;base64,'+base64.b64encode(output.getvalue()).decode()
            except (OSError, ValueError, ImportError):
                pass
    return url if urlsplit(url).scheme in ('http', 'https') else ''


def build(source, left_label='V1', right_label='V2', candidate_dir=None, input_csv=None):
    source = source.resolve()
    if not source.is_relative_to(ROOT/'outputs'):
        raise ValueError('CSV phải nằm trong tool/outputs')
    with source.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        required = {'sample_no', 'entity_name', 'image_url', 'page_url', 'approve_v1', 'approve_v2'}
        if not required <= set(reader.fieldnames or []):
            raise ValueError('CSV thiếu cột so sánh v1/v2')
        rows = list(reader)
    for r in rows:r['comparison_covered']=True
    if candidate_dir is not None:
        from approve_tool import read_csv, CheckError
        manifest=json.loads((candidate_dir/'manifest.json').read_text())
        snapshot=input_csv if input_csv is not None else candidate_dir/'input_snapshot.csv'
        source_rows,_,ids,_,_,sha=read_csv(snapshot)
        if sha!=manifest.get('input_sha256'):raise CheckError('HTML context snapshot mismatch')
        results={}
        for line in (candidate_dir/'results.jsonl').read_text().splitlines():
            value=json.loads(line);i=value['row_index']
            if i in results or not 0<=i<len(ids) or value.get('row_id')!=ids[i]:
                raise CheckError('HTML context row identity mismatch')
            results[i]=value
        if set(results)!=set(manifest['selected_indices']):raise CheckError('HTML candidate chưa hoàn thành')
        compared={int(r['row_index']):r for r in rows}
        wanted={r['image_url'] for r in rows if r['image_url'].strip()}
        for i,value in sorted(results.items()):
            record=source_rows[i]
            if i not in compared and record['image_url'] not in wanted:continue
            if i in compared:
                r=compared[i]
                if any(r[k]!=record[k] for k in ('entity_name','image_url','page_url')) or r['approve_v2']!=value['approve']:
                    raise CheckError('HTML comparison differs from candidate')
            else:
                r={'sample_no':'','row_index':str(i),'entity_id':record['entity_id'],
                   'entity_name':record['entity_name'],'image_url':record['image_url'],'page_url':record['page_url'],
                   'approve_v1':None,'approve_v2':value['approve'],'reason_v1':'','reason_v2':value.get('reason',''),
                   'errors_v2':json.dumps(value.get('errors',[]),ensure_ascii=False),'comparison_covered':False}
                rows.append(r)
            decision=value.get('checks',{}).get('group_decision',{})
            winner=decision.get('winner_row_id')
            r['winner_name']=next((x['entity_name'] for x in results.values() if x['row_id']==winner),'') if winner else ''
            r['branch_identified']=decision.get('proof',{}).get('branch_identified')
    previews={}
    for r in rows:
        if r['image_url'] not in previews:previews[r['image_url']]=preview(r['image_url'])
        r['preview']=previews[r['image_url']]
    data = json.dumps(rows, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    target = source.with_suffix('.html')
    target.write_text(TEMPLATE.replace('__ROWS__', data)
                      .replace('__LEFT_JSON__', json.dumps(left_label, ensure_ascii=False).replace('<', '\\u003c'))
                      .replace('__RIGHT_JSON__', json.dumps(right_label, ensure_ascii=False).replace('<', '\\u003c'))
                      .replace('__LEFT_LABEL__', html.escape(left_label))
                      .replace('__RIGHT_LABEL__', html.escape(right_label)), encoding='utf-8')
    print(f'{target}\n{len(rows)} record; {sum(r["preview"].startswith("data:") for r in rows)} ảnh nhúng offline.')
    return target


TEMPLATE = r'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>So sánh kết quả duyệt ảnh · V1 / V2</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#182738;background:#f3f6fa;font-size:15px}*{box-sizing:border-box}body{margin:0}header{background:#142a40;color:white;padding:28px max(20px,calc((100vw - 1350px)/2))}h1{font-size:26px;margin:0 0 8px}header p{color:#c9d8e8;margin:0;line-height:1.6}.wrap{max-width:1390px;margin:auto;padding:20px}.stats{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 18px}.stat{background:white;border:1px solid #dde5ee;border-radius:10px;padding:12px 18px}.stat b{font-size:23px;margin-right:8px}.tools{position:sticky;top:0;z-index:2;background:#f3f6faf5;backdrop-filter:blur(10px);padding:12px 0;border-bottom:1px solid #dce4ee;display:flex;flex-wrap:wrap;gap:10px;align-items:end}label{display:flex;flex-direction:column;gap:5px;font-size:12px;color:#52647a}input,select,button{font:inherit;border:1px solid #c8d4e1;border-radius:7px;background:white;padding:9px 11px;color:#182738}input[type=search]{min-width:260px;width:100%}.search{flex:1}button{cursor:pointer}button:hover{background:#eaf0f7}.check{flex-direction:row;align-items:center;padding:10px 0;font-size:14px}#count{margin:15px 0;color:#52647a}.record{background:white;border:1px solid #dce4ee;border-radius:12px;margin-bottom:18px;overflow:hidden}.record.changed{border-left:5px solid #d38b19}.record-head{padding:16px 20px;border-bottom:1px solid #e5ebf2;display:flex;gap:12px;align-items:center;flex-wrap:wrap}.record-head h2{font-size:18px;margin:0;flex:1;min-width:200px}.num{color:#65778d;font-variant-numeric:tabular-nums}.body{display:grid;grid-template-columns:minmax(230px,35%) 1fr}.visual{background:#edf1f5;padding:14px;display:flex;flex-direction:column;gap:10px}.visual img{width:100%;height:270px;object-fit:contain;cursor:zoom-in;border-radius:6px;background:#e1e8ef}.links{display:flex;gap:8px;flex-wrap:wrap}.links a{font-size:13px;background:white;border:1px solid #c8d4e1;padding:7px 10px;border-radius:6px;color:#21598c;text-decoration:none}.domain{font-size:12px;color:#546477;overflow-wrap:anywhere}.versions{padding:16px 20px;display:grid;grid-template-columns:1fr 1fr;gap:18px}.version{min-width:0}.version+.version{border-left:1px solid #e2e8ef;padding-left:18px}.version h3{margin:0 0 14px;font-size:14px;color:#64758a}.badge{display:inline-block;border-radius:6px;padding:5px 10px;font-size:13px;font-weight:650}.yes{background:#dff4e8;color:#12603d}.no{background:#fde5e4;color:#9b2827}.blank{background:#edf0f4;color:#536072}.change{background:#fff1d7;color:#875809}.same{background:#edf1f7;color:#657487}.reason{margin:13px 0 5px;line-height:1.6;font-size:14px}.code{font:12px ui-monospace,monospace;color:#738296;overflow-wrap:anywhere}.relation{font-size:13px;margin-top:15px;color:#425a73}details{margin-top:14px;font-size:13px;color:#9a3d26}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}#empty{text-align:center;padding:50px;color:#63778c}dialog{border:0;border-radius:12px;max-width:95vw;max-height:95vh;padding:16px;background:#12283b;color:white}dialog::backdrop{background:#000b}dialog img{display:block;max-width:88vw;max-height:78vh;object-fit:contain;margin:12px auto}dialog .close{float:right}#modalTitle{padding-right:90px;line-height:1.5}@media(max-width:800px){.body{grid-template-columns:1fr}.visual img{height:240px}.wrap{padding:12px}.versions{padding:16px;gap:12px}.version+.version{padding-left:12px}.record-head{padding:14px}.tools{position:static}header{padding:22px 16px}h1{font-size:22px}}
.candidates{min-width:0}.candidate{border-bottom:2px solid #dce4ee}.candidate:last-child{border-bottom:0}.candidate.matched{border-left:4px solid #438eab}.row-meta{padding:10px 20px 0;font-size:13px;overflow-wrap:anywhere}.row-meta a{color:#21598c}.visual{align-self:start;position:sticky;top:90px}.record{overflow:clip}@media(max-width:800px){.visual{position:static}}
</style></head><body>
<header><h1>So sánh kết quả duyệt ảnh</h1><p>Gom theo URL ảnh · <span class="left-label">__LEFT_LABEL__</span> và <span class="right-label">__RIGHT_LABEL__</span> đặt cạnh nhau · Bấm ảnh để phóng to</p></header>
<main class="wrap"><div class="stats" id="stats"></div>
<div class="tools"><label class="search">Tìm tên, URL hoặc lý do<input id="search" type="search" placeholder="Ví dụ: Kim Liên, nhà kính, lỗi…"></label>
<label>Thay đổi<select id="changed"><option value="all">Tất cả record</option><option value="yes">Có đổi nhãn</option><option value="no">Giữ nguyên nhãn</option></select></label>
<label>Nhãn V1<select id="v1"><option value="all">Tất cả</option><option value="yes">yes</option><option value="no">no</option><option value="">Trống</option></select></label>
<label>Nhãn V2<select id="v2"><option value="all">Tất cả</option><option value="yes">yes</option><option value="no">no</option><option value="">Trống</option></select></label>
<label class="check"><input type="checkbox" id="errors">Có lỗi V2</label><button id="reset">Đặt lại</button></div>
<p id="count" aria-live="polite"></p><section id="records"></section><p id="empty" hidden>Không có record phù hợp với bộ lọc.</p>
</main><dialog id="modal"><button class="close" id="close">Đóng ✕</button><div id="modalTitle"></div><img id="large" alt="Ảnh phóng to"></dialog>
<script type="application/json" id="data">__ROWS__</script>
<script>
const rows=JSON.parse(document.getElementById('data').textContent), $=id=>document.getElementById(id);
const LEFT_LABEL=__LEFT_JSON__, RIGHT_LABEL=__RIGHT_JSON__;
const names={IMAGE_NAME_MATCH:'Tên riêng xuất hiện trên ảnh',IMAGE_URL_NAME_MATCH:'Tên xuất hiện trong URL ảnh',PAGE_URL_NAME_MATCH:'Tên xuất hiện trong URL bài viết',URL_SEMANTIC_NAME_MATCH:'Tên trong URL khớp qua so sánh mềm',PAGE_SECTION_MATCH:'Ảnh thuộc mục nói về entity',PAGE_RELATION_MATCH:'Nguồn chứng minh quan hệ thành viên / bộ phận',PAGE_SECTION_OTHER_ENTITY:'Nguồn xác định ảnh thuộc entity khác',NAME_NOT_FOUND:'Đã kiểm tra đủ, không tìm thấy tên',CHECK_INCOMPLETE:'Chưa đủ bằng chứng hoặc kiểm tra chưa hoàn tất',GROUP_OTHER_RECORD_SELECTED:'No theo rule nhóm: một record khác cùng ảnh đã được chọn Yes',GROUP_EXISTING_YES:'Giữ record Yes đầu tiên có sẵn trong nhóm',GROUP_ADDRESS_MATCH:'Chọn chi nhánh có bằng chứng địa chỉ rõ ràng',GROUP_BRAND_FALLBACK:'Chọn đại diện thương hiệu; chưa chứng minh chi nhánh',GROUP_PAGE_NAME_MATCH:'Tên đối tượng được xác minh trong nguồn',GROUP_SOURCE_OTHER_ENTITY:'Nguồn chỉ ra đối tượng khác',EXISTING_LABEL:'Nhãn đã có sẵn'};
Object.assign(names,{USER_MISSING_IMAGE_CONTEXT_YES:'Yes theo rule: không lấy được ngữ cảnh gắn với ảnh',USER_IMAGE_CHECK_ERROR_NO:'No theo rule: lỗi ảnh/OCR',USER_SOURCE_CHECK_ERROR_NO:'No theo rule: lỗi truy cập hoặc trích xuất nguồn',MODEL_SELECTED_YES:'Yes theo ứng viên model đã chọn',MODEL_REJECTED_NO:'No theo đề xuất loại của model',MODEL_DIFFERENT_ENTITY_NO:'No: model xác định đối tượng khác',MODEL_LOCATION_CONFLICT_NO:'No: model xác định mâu thuẫn địa điểm',USER_UNCONFIRMED_BRANCH_YES:'Yes: chung tên/hệ thống, chưa xác minh chi nhánh',USER_GENERIC_DESCRIPTION_YES:'Yes theo rule: nguồn chỉ mô tả chung',USER_MODEL_CHECK_ERROR_NO:'No theo rule: response model không hợp lệ',USER_MODEL_UNCLASSIFIED_NO:'No: response chưa phân loại ứng viên',USER_NO_DECISION_NO:'No: các bước đã kết thúc nhưng chưa có quyết định'});
const relations={same_entity:'Cùng đối tượng',instance_of:'Thành viên của nhóm',part_of:'Bộ phận của đối tượng',same_topic:'Cùng chủ đề',different:'Khác đối tượng',unknown:'Chưa xác định'};
const node=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e};
const covered=r=>r.comparison_covered!==false;
const hasError=r=>{try{return JSON.parse(r.errors_v2||'[]').length>0}catch{return !!r.errors_v2}};
function safeURL(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)?u.href:null}catch{return null}}
function link(label,url){const a=node('a','',label),safe=safeURL(url);if(safe){a.href=safe;a.target='_blank';a.rel='noopener noreferrer'}return a}
function stat(value,label){const e=node('div','stat');e.append(node('b','',value),node('span','',label));$('stats').append(e)}
const grouped=new Map();for(const r of rows){const key=r.image_url.trim()?r.image_url:'missing:'+r.row_index;if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(r)}
const compared=rows.filter(covered);
stat(grouped.size,'nhóm ảnh');stat(rows.length,'record trong nhóm');stat(compared.length,'record có so sánh');stat(compared.filter(r=>r.approve_v1!==r.approve_v2).length,'đổi nhãn');for(const v of ['yes','no',''])stat(rows.filter(r=>r.approve_v2===v).length,RIGHT_LABEL+': '+(v||'trống'));
function version(r,v){const e=node('div','version');if(v==='v1'&&!covered(r)){e.append(node('h3','',LEFT_LABEL),node('p','reason','Không nằm trong pilot cũ — chưa có kết quả để so sánh'));return e;}e.append(node('h3','',v==='v1'?LEFT_LABEL:RIGHT_LABEL),node('span','badge '+(r['approve_'+v]||'blank'),r['approve_'+v]||'Trống'));const reason=r['reason_'+v]||'';e.append(node('p','reason',names[reason]||reason),node('div','code',reason));if(v==='v2'&&r.winner_name)e.append(node('p','relation','Record được chọn trong nhóm: '+r.winner_name));if(v==='v2'&&r.branch_identified===false)e.append(node('p','relation','Đại diện thương hiệu; chưa chứng minh đúng chi nhánh.'));if(v==='v2'&&r.relation_v2)e.append(node('div','relation','Quan hệ: '+(relations[r.relation_v2]||r.relation_v2)));if(v==='v2'&&hasError(r)){const d=node('details');d.append(node('summary','','Xem lỗi V2'));let errors=r.errors_v2;try{errors=JSON.stringify(JSON.parse(errors),null,2)}catch{}d.append(node('pre','',errors));e.append(d)}return e}
function card(group,index,matches){const first=group[0],changed=group.some(r=>covered(r)&&r.approve_v1!==r.approve_v2),e=node('article','record'+(changed?' changed':'')),head=node('div','record-head');head.append(node('h2','','Nhóm ảnh '+index+' · '+group.length+' record'),node('span','badge '+(changed?'change':'same'),changed?'Có đổi nhãn':'Không đổi nhãn trong mẫu'));e.append(head);const body=node('div','body'),visual=node('div','visual'),img=node('img');img.alt='Ảnh chung của nhóm '+index;img.loading='lazy';img.src=first.preview;img.addEventListener('error',()=>{img.hidden=true;visual.prepend(node('p','','Không tải được ảnh. Mở ảnh gốc bên dưới.'))},{once:true});img.addEventListener('click',()=>{$('large').src=first.preview;$('modalTitle').textContent='Nhóm '+index+' · '+group.length+' record';$('modal').showModal()});visual.append(img);const links=node('div','links');links.append(link('Ảnh gốc ↗',first.image_url));visual.append(links,node('div','domain',first.image_url));const winners=group.filter(r=>r.approve_v2==='yes');visual.append(node('p','reason',RIGHT_LABEL+' chọn: '+(winners.map(r=>r.entity_name).join('; ')||'Không có Yes trong nhóm')));visual.append(node('p','domain','Các record ngoài pilot được bổ sung để thấy toàn nhóm. Cột cũ của chúng không có kết quả; không coi là nhãn trống.'));const candidates=node('div','candidates');for(const r of group){const item=node('section','candidate'+(matches.has(r)?' matched':''));const title=node('div','record-head');title.append(node('h2','',r.entity_name),node('span','num',covered(r)?'Pilot #'+r.sample_no:'Ngoài pilot'));if(covered(r))title.append(node('span','badge '+(r.approve_v1!==r.approve_v2?'change':'same'),(r.approve_v1||'Trống')+' → '+(r.approve_v2||'Trống')));item.append(title);const meta=node('div','row-meta');meta.append(node('span','','Dòng dữ liệu '+(Number(r.row_index)+1)+' · '),link('Mở nguồn ↗',r.page_url));item.append(meta);const versions=node('div','versions');versions.append(version(r,'v1'),version(r,'v2'));item.append(versions);candidates.append(item)}body.append(visual,candidates);e.append(body);return e}
function norm(s){return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d')}
function render(){const q=norm($('search').value.trim()),matches=new Set(rows.filter(r=>{const changed=covered(r)&&r.approve_v1!==r.approve_v2;return($('changed').value==='all'||covered(r)&&changed===($('changed').value==='yes'))&&($('v1').value==='all'||covered(r)&&r.approve_v1===$('v1').value)&&($('v2').value==='all'||r.approve_v2===$('v2').value)&&(!$('errors').checked||hasError(r))&&(!q||norm([r.sample_no,r.entity_name,r.page_url,r.image_url,r.reason_v1,r.reason_v2,names[r.reason_v1]||'',names[r.reason_v2]||''].join(' ')).includes(q))}));let index=0;const visible=[];for(const group of grouped.values()){index++;if(group.some(r=>matches.has(r)))visible.push(card(group,index,matches))}$('records').replaceChildren(...visible);$('count').textContent='Hiển thị '+visible.length+' / '+grouped.size+' nhóm; '+matches.size+' record khớp bộ lọc. Giữ toàn bộ record của nhóm để thấy record được chọn và các record No theo rule nhóm. Dòng viền xanh khớp bộ lọc.';$('empty').hidden=visible.length>0}
for(const id of ['search','changed','v1','v2','errors'])$(id).addEventListener('input',render);$('reset').onclick=()=>{$('search').value='';for(const id of ['changed','v1','v2'])$(id).value='all';$('errors').checked=false;render()};$('close').onclick=()=>$('modal').close();$('modal').addEventListener('click',e=>{if(e.target===$('modal'))$('modal').close()});render();
</script></body></html>'''

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', nargs='?', type=Path, default=ROOT/'outputs/pilot_v2/comparison_v1_v2.csv')
    parser.add_argument('--left-label', default='V1')
    parser.add_argument('--right-label', default='V2')
    args=parser.parse_args()
    build(args.csv,args.left_label,args.right_label)
