"""One image observation for visual approval rules and literal OCR."""
import json
from pathlib import Path

from approve_tool import ROOT, CheckError, schema, enum, IDS, atomic_json, digest

VERSION = 'image-quality-ocr-v1'
RULE_PATH = ROOT.parent / 'rule_approve_image.md'
REASONS = ('none', 'large_watermark', 'prominent_contact_overlay', 'advertising_banner',
           'fake_ui', 'screenshot', 'decorative_frame', 'poor_quality', 'subject_obscured',
           'sensitive_personal_document', 'privacy_violation', 'sexual_content',
           'graphic_violence', 'illegal_activity', 'hateful_content',
           'territorial_or_political_violation', 'map_needs_review', 'uncertain_visual')
QUALITY_SCHEMA = schema({
    'status': enum('readable', 'no_text', 'unreadable'), 'texts': IDS,
    'quality_decision': enum('pass', 'reject', 'review'),
    'quality_reason': enum(*REASONS), 'quality_evidence': IDS,
})
INSTRUCTION = '''Inspect ONLY the supplied image. Return literal OCR and a separate visual-quality decision.
OCR: status readable/no_text/unreadable; texts contains literal visible lines, without inferred letters or location.
Apply the user's image approval guidelines:
REJECT: large/dense third-party commercial watermark obscuring the main subject; prominent overlaid sales
phone/Zalo/Facebook/website/QR contact; text-only promotional banner or price flyer; fake play/close controls;
phone/app screenshot with visible interface; thick artificial decorative frame; severe blur/pixelation,
darkness/overexposure/distortion preventing subject recognition; meaningless extreme closeup or selfie
obscuring 80-90% of the place; exposed readable personal documents/bank card/individual identifying invoice;
clear private-space intrusion; sexualized or nude sensitive content, especially involving children;
graphic violence; clearly visible illegal drug use, illicit gambling or threatening weapon activity;
explicit hateful text or clear territorial/political violations as specified by the user's guidelines.
ALLOW: real physical storefront/sign/logo of the place; ordinary brand logos on real objects; unobtrusive
small corner author/news watermark (roughly under 5%, no prominent sales contact); ordinary POI/service
photos, school activities, public crowds and respectful cultural/religious events; nonsexual swimwear in
pool/beach context; normal hotel room interiors are not evidence of privacy intrusion by themselves.
Do not reject just because a logo/text/person/child is present. Distinguish added overlays from physical signs.
Do not infer a person's beliefs, identity, criminal intent or political affiliation from appearance.
If a map or maritime territorial diagram is visible, choose REVIEW/map_needs_review for enlarged manual
inspection unless a violation is unambiguously readable. Do not guess missing islands or tiny markings.
For uncertain violation/insufficient visual detail choose REVIEW, not a speculative reject or pass.
REJECT and REVIEW must have at least one short specific visible evidence description; never invent details.
PASS uses reason none and may have empty evidence. A readable OCR name does not override a rejection.
Do not decide whether this is the requested entity: that is handled later. Do not reject image duplicates;
the user's current same-image multiple-yes policy is handled by separate group logic.
'''


class ImageQualityObserver:
    def __init__(self, inner):
        self.inner = inner
        self.rule_sha = digest(RULE_PATH.read_bytes())

    def ask(self, *args, **kwargs):
        return self.inner.ask(*args, **kwargs)

    def inspect(self, image):
        result = self.inner.ask(VERSION, INSTRUCTION,
                                {'rules_sha256': self.rule_sha}, QUALITY_SCHEMA, image)
        # Validate semantics in addition to the common flat JSON-schema checks.
        decision = result['quality_decision']
        if decision == 'pass' and result['quality_reason'] != 'none':
            raise CheckError('QUALITY_CONTRADICTORY_RESPONSE')
        if decision != 'pass' and (result['quality_reason'] == 'none' or
                                   not any(s.strip() for s in result['quality_evidence'])):
            raise CheckError('QUALITY_MISSING_EVIDENCE')
        return result

    def observe(self, image):
        # Identical prompt/data/image hits the combined observation cache: no
        # second OCR request after the gate has already inspected this image.
        result = self.inspect(image)
        return {k: result[k] for k in ('status', 'texts')}


class ImageQualityGate:
    """Mixin applied before ContinuingPipeline's underlying entity pipeline."""
    def check_group(self, items):
        image = self.fetcher.image(items[0][1]['image_url'])
        inspector = self.client.inner  # SourceSubjectClient(ImageQualityObserver(...))
        observation = inspector.inspect(image)
        url = items[0][1]['image_url']
        proof = {'version': VERSION, 'rules_sha256': inspector.rule_sha,
                 'image_url': url, 'image_sha256': digest(image), **observation}
        folder = self.output_dir / 'quality_checks'
        folder.mkdir(exist_ok=True)
        atomic_json(folder / (digest(url.encode()) + '.json'), proof)
        decision = observation['quality_decision']
        if decision == 'review':
            raise CheckError('IMAGE_QUALITY_REVIEW:' + observation['quality_reason'])
        if decision == 'reject':
            return [{'row_index': i, 'row_id': rid, 'entity_name': row['entity_name'],
                     'approve': 'no', 'reason': 'IMAGE_QUALITY_REJECTED',
                     'checks': {'image_quality': proof}, 'errors': []}
                    for i, row, rid in items]
        results = super().check_group(items)
        for result in results:
            result['checks']['image_quality'] = proof
        return results


def protected_image_urls(csv_path):
    """Protect rejects and pending manual reviews for CSVs within a quality run."""
    output_root = (ROOT / 'outputs').resolve()
    parent = Path(csv_path).resolve().parent
    while parent.is_relative_to(output_root) and parent != output_root:
        folder = parent / 'quality_checks'
        if folder.is_dir():
            blocked = set()
            for path in folder.glob('*.json'):
                result = json.loads(path.read_text())
                if result.get('quality_decision') in ('reject', 'review'):
                    blocked.add(result['image_url'])
            return blocked
        parent = parent.parent
    return set()
