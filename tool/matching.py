"""Conservative fast matches; uncertain names go to the semantic comparator."""
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import unquote


def normalize(value):
    value = unquote(str(value)).casefold().replace('đ', 'd')
    value = ''.join(c for c in unicodedata.normalize('NFKD', value)
                    if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', value).split())


DIGITS = {'khong': 0, 'mot': 1, 'hai': 2, 'ba': 3, 'bon': 4,
          'tu': 4, 'nam': 5, 'lam': 5, 'sau': 6, 'bay': 7, 'tam': 8, 'chin': 9}
NUMBER_WORDS = set(DIGITS) | {'muoi', 'tram', 'linh', 'le'}


def number_value(words):
    # Only number phrases, called for numeric entity identities, not ordinary names.
    if len(words) == 1:
        return DIGITS.get(words[0], 10 if words[0] == 'muoi' else None)
    if 'tram' in words:
        i = words.index('tram')
        if i != 1 or words[0] not in DIGITS:
            return None
        rest = [w for w in words[i+1:] if w not in ('linh', 'le')]
        tail = number_value(rest) if rest else 0
        return DIGITS[words[0]] * 100 + tail if tail is not None else None
    if 'muoi' in words:
        i = words.index('muoi')
        if i > 1 or (i == 1 and words[0] not in DIGITS):
            return None
        tens = DIGITS[words[0]] if i else 1
        tail = words[i+1:]
        if not tail:
            return tens * 10
        if len(tail) == 1 and tail[0] in DIGITS:
            return tens * 10 + DIGITS[tail[0]]
    return None


def numeric_normalize(value):
    tokens = normalize(value).split()
    out, i = [], 0
    while i < len(tokens):
        if tokens[i] not in NUMBER_WORDS:
            out.append(tokens[i]); i += 1; continue
        best = None
        for end in range(i+1, min(len(tokens), i+6)+1):
            if not all(w in NUMBER_WORDS for w in tokens[i:end]):
                break
            n = number_value(tokens[i:end])
            if n is not None:
                best = (end, n)
        if best:
            i, n = best; out.append(str(n))
        else:
            out.append(tokens[i]); i += 1
    return ' '.join(out)


PREFIXES = (
    'toa nha', 'toa cao oc', 'khu do thi', 'san ga', 'san gon', 'san golf',
    'thap nuoc', 'tram bien ap', 'au tau', 'ben do', 'lang', 'phu',
    'hoi thanh tin lanh', 'nha may xu ly nuoc thai', 'nha may nuoc',
    'xa nong thon moi', 'pho di bo', 'duong pho', 'hoi quan',
    'truong mam non', 'truong mau giao', 'truong tieu hoc',
    'truong trung hoc co so', 'truong trung hoc pho thong',
    'truong thcs', 'truong thpt', 'mam non', 'mau giao', 'nha tre',
    'truong mn', 'mn', 'truong', 'trung tam thuong mai', 'nha tho',
    'cong vien', 'san van dong', 'khach san', 'nha hang', 'duong', 'ga', 'cau', 'cho', 'chua',
)
GROUP_PREFIXES = ('khu tap the cu', 'nha kinh', 'nha mang', 'khu dan cu nong thon',
                  'nha o xa hoi')
GENERIC = {'truong', 'mam non', 'mau giao', 'school', 'preschool', 'kindergarten',
           'quoc te', 'international', 'nha tre', 'cau', 'cho', 'chua',
           'thieu nhi', 'tuoi tre', 'van hoa', 'trung tam'}


def profile_name(name, override=None):
    original = normalize(name)
    scope = 'group' if any(original.startswith(p + ' ') or original == p
                          for p in GROUP_PREFIXES) else 'proper_name'
    # Parentheses may hold an alias (Hải Nam), not only an address.
    possible_aliases = []
    for candidate in re.findall(r'\(([^()]*)\)', name):
        value = normalize(candidate)
        if value and not re.search(r'\b(?:quan|huyen|phuong|tp|tinh|thanh pho|ha noi|da nang|q\d+|p\d+)\b', value):
            possible_aliases.append(value)
    core = re.split(r'\s+[-–—]\s+|\s*\(|,', name, maxsplit=1)[0].strip()
    core = normalize(core)
    entity_type = ''
    for prefix in sorted(PREFIXES, key=len, reverse=True):
        if core.startswith(prefix + ' '):
            entity_type = prefix
            core = core[len(prefix):].strip()
            break
    core = re.split(r'\s+(?:quan|huyen|phuong|tp|thanh pho)\s+', core, maxsplit=1)[0]
    for city in ('ha noi', 'da nang', 'ho chi minh'):
        if core.endswith(' ' + city):
            core = core[:-len(city)].strip()
            break
    # A group's geographic/facility scope is essential: Hà Nội alone is not its name.
    if scope == 'group':
        core, possible_aliases = original, []
    if override:
        core = normalize(override.get('core_name', core))
        scope = override.get('scope', scope)
    aliases = [normalize(x) for x in (override or {}).get('aliases', []) if normalize(x)]
    numeric = bool(re.fullmatch(r'\d+(?:\s+(?:thang\s+)?\d+)?', core))
    return {'original': name, 'core_name': core, 'aliases': aliases,
            'entity_type': entity_type, 'requires_type_context': core in GENERIC,
            'possible_aliases': possible_aliases,
            'scope': scope, 'full_name': original,
            'identifying_codes': re.findall(r'\b[a-z]+\d+[a-z]*\b', core),
            'numeric_identity': core if numeric else None,
            'resolved': bool(core and (core not in GENERIC or entity_type))}


def phrase_in(phrase, text):
    return bool(phrase) and (' ' + phrase + ' ') in (' ' + text + ' ')


def exact_match(profile, observed):
    if not profile['resolved']:
        return None
    text = normalize(observed)
    for name in [profile['core_name']] + profile['aliases']:
        if name in GENERIC:
            if not profile.get('entity_type'):
                continue
            name = profile['entity_type'] + ' ' + name
        if re.fullmatch(r'\d+(?:\s+(?:thang\s+)?\d+)?', name):
            target = re.sub(r'\bthang\b', '', name).split()
            # Require school-name context, and do not accept a prefix of another date.
            numtext = numeric_normalize(observed)
            for m in re.finditer(r'\b(?:mam non|mau giao|nha tre|mn|school|preschool|kindergarten)\s+(\d+(?:\s+(?:thang\s+)?\d+)?)(?!\d)', numtext):
                found = re.sub(r'\bthang\b', '', m.group(1)).split()
                if found == target:
                    return {'method': 'numeric_normalization', 'matched_text': m.group(0)}
            continue
        # One very short word (An, My...) is too ambiguous for a raw URL match.
        if len(name.replace(' ', '')) < 4:
            continue
        if phrase_in(name, text):
            return {'method': 'exact', 'matched_text': name}
    return None


def similarity(profile, observed):
    """Diagnostic candidate score only, never a decision threshold."""
    name = profile['core_name']
    words = normalize(observed).split()
    size = max(1, len(name.split()))
    return round(max((SequenceMatcher(None, name, ' '.join(words[i:i+size])).ratio()
                      for i in range(len(words))), default=0), 3)


def numeric_conflict(profile, evidence):
    """Prevent semantic comparator overriding explicit numeric identity differences."""
    codes = profile.get('identifying_codes', [])
    observed_codes = re.findall(r'\b[a-z]+\d+[a-z]*\b', normalize(evidence))
    if codes and observed_codes and not all(c in observed_codes for c in codes):
        return True
    identity = profile.get('numeric_identity')
    if not identity:
        return False
    # Require name context for a numerical name, not unrelated list positions/dates.
    # Allow bare equivalent digits only if surrounded by a known type in the quote.
    if not re.search(r'\b(?:mam non|mau giao|nha tre|mn|school|preschool|kindergarten|'
                     r'cong vien|park|cau|bridge|duong|street|road)\b', normalize(evidence)):
        return True
    expected = re.findall(r'\d+', identity)
    found = re.findall(r'\d+', numeric_normalize(evidence))
    if not found:
        return False  # English number words etc. are left to the semantic comparator.
    return not any(found[i:i+len(expected)] == expected for i in range(len(found)))
