"""Address evidence ranking. Directory-wide mentions never establish an image's branch."""
import re
from matching import normalize,phrase_in


def text_norm(value):
    s=normalize(value)
    s=re.sub(r'\bq\s*(\d+)\b',r'quan \1',s)
    s=re.sub(r'\bp\s*(\d+)\b',r'phuong \1',s)
    s=s.replace('tp hcm','ho chi minh').replace('tphcm','ho chi minh')
    return s


def split_address(name,brand=''):
    # Preserve commas/parentheses while extracting the address; normalize each field later.
    parts=[p.strip() for p in re.split(r'[,()]',name) if p.strip()]
    house=street=''
    for part in parts:
        for m in re.finditer(r'\b(\d+(?:[-/]\d+)*)\s+([^,()]+)',part):
            before=normalize(part[:m.start()])
            if before.endswith(('quan','phuong','huyen','tp','thanh pho','co so','cs')):continue
            value=text_norm(m.group(2));value=re.split(r'\b(?:phuong|quan|huyen|tinh|thanh pho)\b',value)[0].strip()
            if value and any(c.isalpha() for c in value):house,street=text_norm(m.group(1)),value;break
        if house:break
    district=ward=city=''
    for part in parts:
        s=text_norm(part)
        for key,pattern in [('district',r'\b(?:quan|huyen)\s+(.+)'),('ward',r'\bphuong\s+(.+)'),
                            ('city',r'\b(?:tp|thanh pho|tinh)\s+(.+)')]:
            m=re.search(pattern,s)
            if m:
                value=m.group(1).strip()
                if key=='district':district=value
                elif key=='ward':ward=value
                else:city=value
        for known in ('ho chi minh','ha noi','da nang','hai phong','can tho','dong nai','tien giang','binh dinh'):
            if phrase_in(known,s):city=known
    branch=text_norm(parts[0]) if parts else ''
    if brand and branch.startswith(normalize(brand)+' '):branch=branch[len(normalize(brand)):].strip()
    if house or branch==normalize(brand):branch=''
    if len(branch.split())<2:branch=''
    return {'original':name,'house_number':house,'street':street,'branch':branch,
            'district':district,'ward':ward,'city':city}


def rank_addresses(candidates,contexts,identity_ids,strict_branch=False):
    """Only a unique, strong address in image-linked context can identify a branch.

    candidates: [{record_id,address}]; contexts: [{text,evidence_ids,scope}].
    Multiple candidate addresses in one context => directory ambiguity, not a best-score vote.
    """
    audits=[];claims=[]
    cities={a['address']['city'] for a in candidates if a['address']['city']}
    for context in contexts:
        text=text_norm(context['text']);found_cities={c for c in cities if phrase_in(c,text)}
        scores=[]
        for item in candidates:
            a=item['address'];score=0;matched=[];conflicts=[]
            if a['city'] and len(found_cities)==1 and a['city'] not in found_cities:conflicts.append('different_city')
            if a['street'] and phrase_in(a['street'],text):
                score+=12;matched.append('street')
                if a['house_number'] and phrase_in(a['house_number']+' '+a['street'],text):
                    score+=28;matched.append('house_number')
                elif a['house_number']:
                    at=text.find(a['street']);m=re.search(r'(\d+(?:\s+\d+)?)\s*$',text[max(0,at-25):at])
                    if m and m.group(1)!=a['house_number']:conflicts.append('different_house_number')
            branch=a['branch']
            if strict_branch:
                # A city (including its spelling in branch) is not a facility name.
                for city in cities | {'sai gon','ho chi minh','ha noi','da nang','hai phong','can tho'}:
                    branch=re.sub(r'\b'+re.escape(city)+r'\b',' ',branch)
                branch=re.sub(r'\b(?:tp|thanh pho|tinh|quan|huyen|phuong|xa)\b',' ',branch)
                branch=' '.join(branch.split())
            if branch and phrase_in(branch,text):
                # Administrative fragments are useful context, never a unique branch vote.
                admin=bool(re.match(r'^(?:quan|huyen|phuong|xa)\b',a['branch']))
                if not (strict_branch and admin):score+=30;matched.append('branch')
            for field,weight in [('district',2),('ward',1),('city',3)]:
                if a[field] and phrase_in(a[field],text):score+=weight;matched.append(field)
            if conflicts:score=0
            scores.append({'record_id':item['record_id'],'score':score,'matched':matched,'conflicts':conflicts})
        strong=[r for r in scores if r['score']>=30 and r['record_id'] in identity_ids]
        audit={**context,'scores':scores,'ambiguous':len(strong)>1}
        audits.append(audit)
        if len(strong)==1:claims.append({'record_id':strong[0]['record_id'],'score':strong[0]['score'],
            'evidence_ids':context['evidence_ids'],'context':context['text']})
    winners={r['record_id'] for r in claims}
    # Conflicting image occurrences or a directory listing cannot establish one branch.
    if len(winners)==1 and not any(a['ambiguous'] for a in audits):
        winner=max(claims,key=lambda r:r['score']);return winner,audits
    return None,audits
