"""Conservative, local-only alias expansion after a group has a confirmed YES."""
import re
from matching import normalize
from propagate_group_yes import relation, location_phrases, CITIES

VERSION = 'group-aliases-v1'


def compatible_alias(a, b, places=()):
    na, nb = normalize(a), normalize(b)
    # Reviewed aliases: these name the whole Times City site, not a shop/phase/lake.
    def times_city(n):
        n=re.sub(r'^(?:khu do thi|khu|chung cu)\s+', '', n)
        n=n.replace('times city vinhomes times city', 'vinhomes times city')
        return bool(re.fullmatch(r'(?:vinhomes )?times city(?: hai ba trung)?(?: ha noi)?', n))
    if times_city(na) and times_city(nb):return 'reviewed_times_city_alias'
    if na==nb:return 'same_normalized_full_name'
    for value,other in ((a,nb),(b,na)):
        for suffix in re.split(r'\s+[-–—]\s+',value)[1:]:
            n=normalize(suffix)
            if n not in other and n not in CITIES and not re.match(r'^(?:quan|huyen|phuong|xa|tinh|tp|thanh pho)\b',n):
                return None
    # Do not conflate a site with its component, or two named places joined by a dash.
    for prefix in ('ho ', 'cong vien ', 'san ga ', 'ga ', 'dai tuong niem ', 'nghia trang '):
        if na.startswith(prefix) != nb.startswith(prefix):
            if prefix in ('ho ', 'cong vien ', 'dai tuong niem ', 'nghia trang '):return None
            if {na.split()[0],nb.split()[0]} == {'ga','san'}:return None
    for value in (na,nb):
        if re.search(r'\b(?:ben vat cach|khu b|park hill premium)\b',value):
            if na!=nb:return None
    if ('cai mep thi vai' in na) != ('cai mep thi vai' in nb):return None
    # The former heuristic treats any multiword suffix as a place; require its
    # actual administrative syntax for automatic use in the runner.
    known_places={p for p in places if re.search(r'\b(?:quan|huyen|phuong|xa|tinh|thanh pho)\b',p)}
    return relation(a,b,known_places)


def expand_group_yes(items, answers):
    by_id={r['row_id']:r for r in answers}
    original={rid:row for _,row,rid in items}
    rows=[row for _,row,_ in items]
    places=location_phrases(rows)
    anchors=[rid for _,_,rid in items if by_id[rid]['approve']=='yes' and not by_id[rid].get('errors')]
    for _,row,rid in items:
        target=by_id[rid]
        # Explicit model negatives, errors and existing manual labels take priority.
        if row.get('approve') or target['approve']!='no' or target['reason']!='GROUP_OTHER_RECORD_SELECTED':continue
        if target.get('errors') or not row['image_url'].strip():continue
        for aid in anchors:
            anchor=original[aid]
            if anchor['image_url']!=row['image_url']:continue
            why=compatible_alias(anchor['entity_name'],row['entity_name'],places)
            if not why:continue
            before={'approve':target['approve'],'reason':target['reason']}
            target.update(approve='yes',reason='GROUP_EQUIVALENT_ENTITY_YES')
            target['checks']['group_alias']={'version':VERSION,'anchor_row_id':aid,
                'anchor_entity_name':anchor['entity_name'],'relation':why,'before':before,
                'policy':'original final yes anchors only; no transitive expansion'}
            break
    return answers
