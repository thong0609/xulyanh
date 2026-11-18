"""Conservative Qwen policy: verified names, bounded source chunks, explicit coverage."""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from difflib import SequenceMatcher
from approve_tool import (ModelClient, CheckError, MATCH_SCHEMA, PAGE_SCHEMA, evidence_present,
                          resolve_evidence, identity_supported as legacy_identity)
from matching import exact_match, normalize, profile_name, numeric_conflict

POLICY_VERSION = 'qwen-policy-fast2'
NAME_SCHEMA = {'type':'object', 'additionalProperties':False, 'properties': {
    k: MATCH_SCHEMA['properties'][k] for k in ('status','evidence_ids','observed_name','name_relation')},
    'required':['status','evidence_ids','observed_name','name_relation']}
CHUNK_SCHEMA = {'type':'object', 'additionalProperties':False, 'properties': {
    k: v for k,v in PAGE_SCHEMA['properties'].items() if k not in ('context_index','explanation')},
    'required':[k for k in PAGE_SCHEMA['required'] if k not in ('context_index','explanation')]}


def verified_identity(profile, result, selected, supporting=()):
    name = result['observed_name']
    if not evidence_present(name, [b['text'] for b in selected]): return False
    if numeric_conflict(profile, name): return False
    if exact_match(profile, name): return True
    # An explicit alias/translation mapping or source statement can prove equivalence.
    if result['name_relation'] in ('alias','translation'):
        return legacy_identity(profile, {**result, 'name_relation':'alias'}, selected, supporting)
    if result['name_relation'] != 'ocr_variant' or profile.get('scope') == 'group': return False
    # One character edit in a long multiword name, preserving all numeric tokens/codes.
    # This is deliberately narrower than fuzzy similarity over an entire caption.
    target, observed = profile['core_name'], normalize(name)
    a, b = target.split(), observed.split()
    if (len(target.replace(' ','')) < 10 or len(a) < 2 or len(a) != len(b)
            or not any(x == y for x,y in zip(a,b))
            or re.findall(r'\b\w*\d\w*\b', target) != re.findall(r'\b\w*\d\w*\b', observed)):
        return False
    edits = sum(max(i2-i1,j2-j1) for op,i1,i2,j1,j2 in
                SequenceMatcher(None,target,observed,autojunk=False).get_opcodes() if op!='equal')
    return edits == 1


def uncertain(reason):
    return {'status':'uncertain','evidence_ids':[],'observed_name':'',
            'name_relation':'not_applicable','context_index':-1,'explanation':reason,
            'relation':'unknown','scope_status':'unknown','supporting_evidence_ids':[],
            'visual_status':'not_checked'}


def packed(blocks, chars):
    batch, size = [], 0
    for block in blocks:
        cost = len(block['text']) + 80
        if batch and size + cost > chars:
            yield batch
            batch, size = [], 0
        batch.append(block); size += cost
    if batch: yield batch


class ConservativeQwenPolicy(ModelClient):
    identity_supported = staticmethod(verified_identity)
    page_chunk_chars = 2200
    max_page_calls = 24

    def compare(self, profile, texts, context):
        blocks = [{'id':f'obs_{i}', 'text':t, 'context_index':-1, 'field':'observed'}
                  for i,t in enumerate(texts) if t.strip()]
        result = self.ask('verify_name_fast2',
            'Check ONLY whether an observed string contains the entity name. '
            'Entity is the query, NEVER evidence. Copy observed_name from an observed block. '
            'No name in these strings => not_match, even if the unvisited webpage may contain it. '
            'Logos, publishers, slogans and bare years are not entity names. '
            'Example: entity Lakeview City, observed Safety First => not_match. '
            'Example: entity school 8, observed school 18 => not_match. '
            'Example: entity school 19/5, observed school nineteen May => number_equivalent candidate. '
            'Translations/aliases need supplied mapping; different Vietnamese names are not translations. '
            'For match provide actual observed_name and its block IDs. For not_match use empty name, '
            'empty IDs and not_applicable. No explanations.',
            {'entity':profile, 'observed_blocks':blocks, 'context':context}, NAME_SCHEMA)
        result = dict(result, explanation='Qwen compact name check')
        selected = resolve_evidence(result['evidence_ids'], blocks, 'MATCH_EVIDENCE_INVALID')
        result.update(evidence_blocks=selected, evidence='\n'.join(b['text'] for b in selected))
        if result['status'] == 'match' and not verified_identity(profile,result,selected):
            result.update(status='uncertain', validation_reason='NAME_EQUIVALENCE_UNVERIFIED')
        # Do not trust a negative answer that overlooks a directly verifiable name.
        if result['status'] == 'not_match':
            for b in blocks:
                if exact_match(profile,b['text']):
                    result.update(status='match', observed_name=b['text'], name_relation='exact',
                                  evidence_ids=[b['id']], evidence_blocks=[b], evidence=b['text'])
                    break
        return result

    def assess_page(self, profile, page, image=None):
        blocks = self.page_blocks(page)
        context_blocks = [[b for b in blocks if b['context_index']==i]
                          for i in range(len(page['contexts']))]
        global_blocks = [b for b in blocks if b['context_index']==-1]
        # Verified image occurrences first; global text is never primary image evidence.
        jobs = [(i,chunk) for i,bs in enumerate(context_blocks)
                for chunk in packed(bs,self.page_chunk_chars)]
        jobs += [(-1,chunk) for chunk in packed(global_blocks,self.page_chunk_chars)]
        history, calls, covered = [], 0, set()
        all_absent = bool(jobs)
        def finish(result, complete=False):
            result['chunk_audit'] = {'policy':POLICY_VERSION,'calls':calls,
                'covered_blocks':len(covered),'total_blocks':len(blocks),
                'all_blocks_checked':complete, 'checks':history}
            return result

        while jobs:
            if calls >= self.max_page_calls:
                return finish(uncertain('PAGE_CHUNK_CALL_LIMIT'))
            index, chunk = jobs.pop(0)
            if index < 0 and (not all_absent or profile.get('scope')=='group' or
                    any(page.get(k) for k in ('incomplete','truncated','contexts_truncated')) or
                    any(c.get('local_truncated') for c in page['contexts'])):
                # Global text cannot rescue an unresolved image association. Do not spend
                # GPU calls proving absence when a safe negative is already impossible.
                return finish(uncertain('PAGE_ABSENCE_NOT_PROVABLE'))
            # Short IDs reduce accidental quotations or fabricated long IDs in Qwen output.
            mapping = {f'E{n}':b for n,b in enumerate(chunk)}
            calls += 1
            try:
                raw = self.ask('page_chunk_fast2',
                    'Review this source excerpt. Entity is a query, never evidence. '
                    'Blocks marked context are from an occurrence of the target image; '
                    'page-only blocks cannot prove what the image shows. '
                    'match: context identifies the same entity or a proven member of its group. '
                    'Copy the FULL subject name including type into observed_name. '
                    'Use ONLY supplied E IDs, never quotes. Supporting IDs prove aliases/group qualifiers. '
                    'A logo, publisher, slogan, generic activity or year is not an entity name. '
                    'Translation is NOT permission to equate different names. '
                    'For groups all type/location/facility qualifiers need explicit evidence; '
                    'a larger area containing the requested facility is not its member. '
                    'other_entity: own caption/heading explicitly identifies a different entity, '
                    'not just an unrelated name elsewhere. relation must be different. '
                    'name_not_found: no name/alias/member evidence in THIS excerpt; empty IDs/name. '
                    'uncertain: ambiguous or insufficient association. '
                    'No image => visual_status not_checked. Keep all required fields, no explanation.',
                    {'entity':profile,'purpose':'image_context' if index>=0 else 'page_only',
                     'blocks':[{'id':key,'text':b['text'],'field':b['field'],
                                'context':b['context_index']>=0} for key,b in mapping.items()]},
                    CHUNK_SCHEMA, image if profile.get('scope')=='group' and index>=0 else None)
                # Never silently ignore unknown IDs; validators must see this as an error.
                raw = dict(raw)
                for field in ('evidence_ids','supporting_evidence_ids'):
                    if any(key not in mapping for key in raw[field]):
                        raise CheckError('PAGE_EVIDENCE_INVALID')
                    raw[field] = [mapping[key]['id'] for key in raw[field]]
                raw.update(context_index=index, explanation='Validated source chunk')
                # Absence here applies only to this chunk, not the complete page yet.
                if raw['status']=='name_not_found':
                    if any(exact_match(profile,b['text']) for b in chunk):
                        raw = uncertain('NAME_PRESENT_IN_CHUNK')
                    decision = raw
                elif index < 0:
                    decision = uncertain('NAME_OR_RELATION_IN_PAGE_WITHOUT_IMAGE_CONTEXT')
                else:
                    decision = self.validate_page(profile,page,raw,chunk,image)
                    if decision['status']=='match':
                        if profile.get('scope') != 'group':
                            if decision['relation'] != 'same_entity' or not verified_identity(
                                    profile,decision,decision['evidence_blocks'],decision['supporting_evidence_blocks']):
                                decision.update(status='uncertain',validation_reason='NAME_EQUIVALENCE_UNVERIFIED')
                        else:
                            # Conservative coverage of required group qualifiers in cited source.
                            required = set(normalize(profile['original']).split())
                            evidence = ' '.join(b['text'] for b in decision['evidence_blocks']+
                                                decision['supporting_evidence_blocks'])
                            if not required.issubset(set(normalize(evidence).split())):
                                decision.update(status='uncertain',validation_reason='GROUP_QUALIFIERS_UNPROVEN')
                    if decision['status']=='other_entity':
                        subject = profile_name(decision['observed_name'])
                        own_label = any(b['field'] in ('alt','headings') and
                            evidence_present(decision['observed_name'],[b['text']])
                            for b in decision['evidence_blocks'])
                        if (not own_label or not profile.get('entity_type') or
                                subject['entity_type'] != profile['entity_type'] or
                                verified_identity(profile,decision,decision['evidence_blocks'])):
                            decision.update(status='uncertain',validation_reason='CONTRADICTION_UNPROVEN')
                covered.update(b['id'] for b in chunk)
                history.append({'context_index':index,'blocks':[b['id'] for b in chunk],
                                'status':decision['status'], 'validation_reason':decision.get('validation_reason'),
                                'observed_name':decision.get('observed_name'),
                                'name_relation':decision.get('name_relation'),
                                'evidence_ids':decision.get('evidence_ids',[])})
                if decision['status'] in ('match','other_entity'):
                    return finish(decision)
                all_absent = all_absent and decision['status']=='name_not_found'
            except CheckError as error:
                if str(error)=='LOCAL_CONTEXT_TOO_LONG' and len(chunk)>1:
                    middle=len(chunk)//2
                    jobs[0:0]=[(index,chunk[:middle]),(index,chunk[middle:])]
                    history.append({'context_index':index,'error':str(error),'action':'split_and_retry'})
                    continue
                all_absent=False
                history.append({'context_index':index,'error':str(error),'blocks':[b['id'] for b in chunk]})
        complete = len(covered)==len(blocks) and bool(blocks)
        if (complete and all_absent and profile.get('scope')!='group'
                and not any(page.get(k) for k in ('incomplete','truncated','contexts_truncated'))
                and not any(c.get('local_truncated') for c in page['contexts'])):
            result=uncertain('All supplied source blocks checked; no name found')
            result['status']='name_not_found'
            return finish(result,True)
        return finish(uncertain('PAGE_CHECK_UNRESOLVED'),complete)
