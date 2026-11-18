"""Opt-in source classification refinement; one source request, unchanged OCR and URL rules."""
import copy
from approve_tool import TEXT, IDS, enum
from matching import normalize, profile_name, exact_match, phrase_in

VERSION = 'image-subject-guard-v2'
EXTRA = {
    'image_subject_name': TEXT,
    'image_subject_type': TEXT,
    'image_subject_quote': TEXT,
    'image_subject_evidence_ids': IDS,
    'image_subject_binding': enum('caption', 'alt', 'local_sentence', 'unbound'),
    'image_subject_other_candidate_ids': IDS,
    'image_subject_type_conflict_ids': IDS,
    'generic_reason': TEXT,
}
INSTRUCTION = (
    '\nSOURCE SUBJECT PRIORITY (required): Before classifying candidates, identify the entity explicitly '
    'bound to THIS image in its caption, alt or an image-local sentence. A school caption such as '
    '"Tiết dạy học tại Trường Mẫu giáo La Dạ" establishes that school; candidates naming other schools '
    'are different_entity_ids, NEVER generic_description_ids, even if the article discusses education generally. '
    'Apply the SAME decision to all candidates that differ from that identified school, across source variants. '
    'A name mentioned only elsewhere in the article, navigation or a list of nearby places is unbound: '
    'do not use it to reject the image. Distinguish different ENTITY TYPES from missing branches: a power '
    'transmission line is not an electrical substation; a park is not a pumping station. Shared system, '
    'voltage or city cannot make those an unconfirmed branch. Reject such candidates when the image-local '
    'source establishes the incompatible type. A genuinely unspecified branch of the SAME type/brand '
    'remains unconfirmed_branch_ids (YES). Do NOT treat compatible accommodation/scene descriptions '
    'as different entities: a villa, room, lobby or pool can belong to the same named hotel/resort. '
    'For example, "Ảnh chụp villa Mường Thanh Mộc Châu số 3" is compatible with '
    '"Resort Mường Thanh Holiday Mộc Châu" when no different operator/location is established: '
    'allow the shortened name or unconfirmed branch (YES). A photo ordinal such as "ảnh số 3" '
    'does not establish a different facility. Likewise an architectural component is not automatically '
    'a different site. Keep true role conflicts such as transmission line versus substation as NO. '
    'Truly generic descriptions without an identified different '
    'image subject remain generic_description_ids (YES). Preserve aliases and translations. '
    'Fill image_subject_name/type and copy ONE short verbatim quote (up to 200 characters) with real block '
    'IDs proving that image subject. Use binding unbound and empty quote/IDs if no such evidence exists. '
    'image_subject_other_candidate_ids and image_subject_type_conflict_ids list only supplied candidate '
    'IDs contradicted by that bound evidence; also put them in different_entity_ids or rejected_ids. '
    'If generic_description_ids is nonempty, generic_reason must explain why no image-bound different '
    'entity/type has been established. Never classify explicit other-school captions as generic.'
)


def kind(value):
    n = normalize(value)
    if any(phrase_in(x, n) for x in ('tram bien ap', 'substation')):
        return 'substation'
    if any(phrase_in(x, n) for x in ('duong day', 'transmission line', 'power line')):
        return 'power_line'
    if any(phrase_in(x, n) for x in ('truong', 'mam non', 'mau giao', 'school', 'preschool', 'kindergarten')):
        return 'school'
    if any(phrase_in(x, n) for x in ('tram bom', 'pumping station')):
        return 'pump'
    if any(phrase_in(x, n) for x in ('cong vien', 'park')):
        return 'park'
    return ''


def refine(answer, data):
    result = copy.deepcopy(answer)
    candidates = {c['record_id']: c['entity'] for c in data['candidates']}
    blocks = {b['id']: b for b in data['blocks']}
    refs = answer['image_subject_evidence_ids']
    quote = answer['image_subject_quote']
    subject = answer['image_subject_name']
    # Only a literal quote in an image-local text/alt block can trigger an override.
    normquote = ' '.join(quote.split()).casefold()
    verified = bool(normquote and subject and answer['image_subject_binding'] != 'unbound'
                    and refs and all(x in blocks for x in refs)
                    and any(blocks[x].get('field') in ('local_text', 'alt')
                            and normquote in ' '.join(blocks[x]['text'].split()).casefold() for x in refs)
                    and phrase_in(normalize(subject), normalize(quote)))
    claimed = set(answer['image_subject_other_candidate_ids'] + answer['image_subject_type_conflict_ids'])
    if not claimed.issubset(candidates):
        from approve_tool import CheckError
        raise CheckError('GROUP_CANDIDATE_INVALID')
    denied = set()
    why = {}
    if verified:
        subject_kind = kind(subject+' '+answer['image_subject_type'])
        for cid, profile in candidates.items():
            candidate_kind = kind(profile['original'])
            if cid in claimed:
                denied.add(cid)
                why[cid] = 'model_explicit_image_subject_conflict'
            if subject_kind and candidate_kind and subject_kind != candidate_kind:
                denied.add(cid)
                why[cid] = 'image_subject_type_conflict'
            equivalent_winner = (cid == answer['winner_id'] and answer['name_relation'] in
                                 ('alias', 'translation', 'ocr_variant', 'number_equivalent'))
            if subject_kind == candidate_kind == 'school' and not equivalent_winner and not exact_match(profile, subject):
                # School names must agree; common words like "mầm non" are insufficient.
                observed = profile_name(subject)
                if observed['core_name'] != profile['core_name']:
                    denied.add(cid)
                    why[cid] = 'image_caption_names_other_school'
    result['different_entity_ids'] = sorted(set(result['different_entity_ids']) | denied)
    for field in ('generic_description_ids', 'unconfirmed_branch_ids'):
        result[field] = [cid for cid in result[field] if cid not in denied]
    if result['winner_id'] in denied:
        result['winner_id'] = ''
    result['source_subject_guard'] = {
        'version': VERSION, 'evidence_verified': verified,
        'overridden_candidate_ids': sorted(denied), 'reasons': why,
        'original_generic_ids': answer['generic_description_ids'],
        'original_unconfirmed_branch_ids': answer['unconfirmed_branch_ids'],
    }
    return result


class SourceSubjectClient:
    def __init__(self, inner):
        self.inner = inner

    def observe(self, image):
        return self.inner.observe(image)

    def ask(self, task, instruction, data, output_schema, image=None):
        if task not in ('group_source_user_rules_v4','group_source_user_rules_v5'):
            return self.inner.ask(task, instruction, data, output_schema, image)
        schema = copy.deepcopy(output_schema)
        schema['properties'].update(EXTRA)
        schema['required'] = list(schema['properties'])
        improved=task=='group_source_user_rules_v5'
        extra_instruction=(' V5: Generic or same-system descriptions never override an explicit different '
            'location, named facility or role. An airport-services company is not the airport. A railway '
            'line is not a particular station. A named airport terminal is a compatible component of '
            'the same airport, not a different operator. OCR signs on buses/background buildings may be '
            'route destinations or nearby places; do not guess the subject from them. Use the image-local '
            'caption/alt to distinguish these cases. Generic YES is allowed only after checking for '
            'these conflicts.' if improved else '')
        answer = self.inner.ask('group_source_subject_guard_v3' if improved else 'group_source_subject_guard_v2', instruction+INSTRUCTION+extra_instruction,
                                data, schema, image)
        return refine_v3(answer,data) if improved else refine(answer, data)


def role(value):
    import re
    n=normalize(value)
    if 'cong ty' in n and any(x in n for x in ('san bay','hang khong')):return 'airport_company'
    if re.search(r'\b(?:nha ga|ga)\b',n) and any(x in n for x in ('metro','duong sat','cat linh','yen nghia')):return 'rail_station'
    if any(x in n for x in ('duong sat','railway line','metro line')):return 'rail_line'
    if 'nha ga' in n and any(x in n for x in ('hanh khach','quoc te','san bay','phu bai','cam ranh','noi bai')):return 'airport_terminal'
    if any(x in n for x in ('san bay','cang hang khong','airport')):return 'airport'
    return kind(value)


def same_airport_component(candidate,subject):
    import re
    if role(candidate)!='airport' or role(subject)!='airport_terminal':return False
    def core(value):
        n=normalize(value)
        n=re.sub(r'\b(?:nha ga|san bay|cang hang khong|quoc te|hanh khach|terminal|international|airport|t\s*\d+)\b',' ',n)
        return ' '.join(n.split())
    a,b=core(candidate),core(subject)
    return len(a.replace(' ',''))>=4 and phrase_in(a,b)


def refine_v3(answer,data):
    result=refine(answer,data)
    audit=result['source_subject_guard']
    audit['version']='image-subject-guard-v3'
    if not audit['evidence_verified']:return result
    subject=answer['image_subject_name']
    sr=role(subject+' '+answer['image_subject_type'])
    for c in data['candidates']:
        cid=c['record_id'];name=c['entity']['original'];cr=role(name)
        if same_airport_component(name,subject) and cid not in answer['location_conflict_ids']:
            # A terminal can depict its named airport; preserve true location negatives.
            for field in ('different_entity_ids','rejected_ids','image_subject_type_conflict_ids','image_subject_other_candidate_ids'):
                result[field]=[x for x in result[field] if x!=cid]
            if not result['winner_id'] and cid not in result['generic_description_ids']:
                result['generic_description_ids'].append(cid)
            audit['overridden_candidate_ids']=[x for x in audit['overridden_candidate_ids'] if x!=cid]
            audit['reasons'].pop(cid,None)
            audit.setdefault('compatible_component_ids',[]).append(cid)
            continue
        if (sr,cr) in {('rail_line','rail_station'),('airport','airport_company'),
                        ('airport_terminal','airport_company'),('airport_company','airport')}:
            result['different_entity_ids']=sorted(set(result['different_entity_ids'])|{cid})
            for field in ('generic_description_ids','unconfirmed_branch_ids'):
                result[field]=[x for x in result[field] if x!=cid]
            if result['winner_id']==cid:result['winner_id']=''
            audit['overridden_candidate_ids']=sorted(set(audit['overridden_candidate_ids'])|{cid})
            audit['reasons'][cid]='explicit_site_role_conflict'
    return result
