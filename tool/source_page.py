"""Small DOM extractor with image-local context, using the standard library."""
from html.parser import HTMLParser
from urllib.parse import urljoin, urldefrag, urlsplit, urlunsplit, unquote
import unicodedata
import re


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def text(self):
        return ' '.join(' '.join(c.text() if isinstance(c, Node) else c
                                for c in self.children).split())

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()


class DOM(HTMLParser):
    VOID = {'img', 'source', 'br', 'hr', 'meta', 'link', 'input', 'wbr', 'area', 'base', 'embed'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('document'); self.current = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in self.VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent; return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def clean(node):
    kept = []
    for child in node.children:
        if isinstance(child, Node):
            classes = ' '.join(str(child.attrs.get(k, '') or '') for k in ('class', 'id'))
            if child.tag in {'script', 'style', 'nav', 'footer', 'aside', 'noscript'}:
                continue
            if re.search(r'\b(?:related|recommendations|sidebar|advertisement|cookie-banner|toc|toc_body|table-of-contents|ez-toc-container)\b', classes, re.I):
                continue
            clean(child)
        kept.append(child)
    node.children = kept


def url_identity(url):
    """Conservative equivalence: Unicode and known CDN wrappers; preserve query IDs."""
    url = unicodedata.normalize('NFC', unquote(urldefrag(url)[0]))
    parts = urlsplit(url)
    if '/cdn-cgi/image/' in parts.path:
        # Cloudflare format /cdn-cgi/image/<options>/<absolute original URL>.
        wrapped = parts.path.split('/cdn-cgi/image/', 1)[1].split('/', 1)
        if len(wrapped) == 2 and wrapped[1].startswith(('https://', 'http://')):
            return url_identity(wrapped[1] + ('?' + parts.query if parts.query else ''))
    path, host = parts.path, parts.netloc.casefold()
    if re.fullmatch(r'res(?:-\d+)?\.cloudinary\.com', parts.hostname or ''):
        host = 'res.cloudinary.com'
        # Only remove recognizable transformation segments, not public IDs/version.
        path = re.sub(r'(/image/upload/)(?:(?:[a-z]{1,3}_[^/]+)(?:/|$))+', r'\1', path)
    scheme = 'https' if parts.scheme.casefold() in ('http', 'https') else parts.scheme.casefold()
    return urlunsplit((scheme, host, path, parts.query, ''))


def srcset_urls(value):
    # Commas may occur INSIDE an unquoted CDN URL. Descriptors separate candidates.
    for match in re.finditer(r'(\S+)(?:\s+(?:\d+w|[\d.]+x))?(?:\s*,\s*|\s*$)', value):
        candidate = match.group(1).rstrip(',')
        if candidate:
            yield candidate


def image_urls(node, base):
    values = [node.attrs.get(k, '') or '' for k in
              ('src', 'data-src', 'data-original', 'data-lazy-src', 'content')]
    for attr in ('srcset', 'data-srcset'):
        values.extend(srcset_urls(node.attrs.get(attr, '') or ''))
    parent = node.parent
    while parent and parent.tag in ('picture', 'a', 'span'):
        if parent.tag == 'a':
            href = parent.attrs.get('href', '') or ''
            if re.search(r'\.(?:jpe?g|png|webp|gif|avif)(?:[?#]|$)', href, re.I):
                values.append(href)
        parent = parent.parent
    return [urldefrag(urljoin(base, v.strip()))[0] for v in values
            if v.strip() and not v.lstrip().startswith('data:')]


def ancestors(node):
    while node:
        yield node
        node = node.parent


def is_card(node):
    # Exact class tokens. card-img-top/card-body are parts, not entity containers.
    classes = set((node.attrs.get('class', '') or '').casefold().split())
    return bool(classes & {'card', 'school-item', 'school-card', 'result-item',
                           'listing-item', 'search-result', 'entity-card'})


def card_owner(node):
    return next((n for n in ancestors(node) if is_card(n)), None)


def article_owner(node):
    return next((n for n in ancestors(node) if n.tag == 'article'), None)


def extract_page(html, page_url, target_url, max_chars=24000):
    dom = DOM(); dom.feed(html)
    clean(dom.root)
    mains = [n for n in dom.root.walk() if n.tag == 'main']
    articles = [n for n in dom.root.walk() if n.tag == 'article']
    root = max(mains, key=lambda n: len(n.text())) if mains else (articles[0] if len(articles) == 1 else dom.root)
    text = root.text()
    blocked = any(s in text.casefold() for s in (
        'verify you are human', 'checking your browser', 'enable javascript and cookies',
        'access denied', 'just a moment...')) or bool(
            len(text)<1000 and re.search(r'\bcaptcha\b',text.casefold()))
    access_blocked=blocked or any(s in text.casefold() for s in (
        'subscribe to continue', 'đăng nhập để đọc tiếp', 'enable javascript'))
    incomplete = access_blocked or len(text) < 180
    target = url_identity(target_url)
    nodes = list(root.walk())
    positions = {id(n): i for i, n in enumerate(nodes)}
    # Text events with DOM position avoid repeating descendant text.
    events = []
    def collect(n):
        for child in n.children:
            if isinstance(child, Node): collect(child)
            elif child.strip(): events.append((positions[id(n)], child.strip(), n))
    collect(root)
    contexts = []
    for pos, node in enumerate(nodes):
        if node.tag not in ('img', 'source'):
            continue
        candidates = image_urls(node, page_url)
        matched = next((u for u in candidates if url_identity(u) == target), None)
        if not matched: continue
        card = card_owner(node)
        figure = next((n for n in ancestors(node) if n.tag == 'figure'), None)
        owner = article_owner(node)
        headings = []
        for i, previous in enumerate(nodes[:pos]):
            if not re.fullmatch('h[1-6]', previous.tag): continue
            if card_owner(previous) is not card: continue
            if article_owner(previous) is not owner: continue
            level = int(previous.tag[1])
            headings = [(l, t, p) for l, t, p in headings if l < level]
            headings.append((level, previous.text(), i))
        if card:
            # Card title often follows its image. Never inherit previous card title.
            titles = [n.text() for n in card.walk() if re.fullmatch('h[1-6]', n.tag)]
            local, scope = card.text(), 'card'
            heading_texts = titles
        else:
            heading_texts = [t for _, t, _ in headings]
            start = headings[-1][2] if headings else 0
            level = headings[-1][0] if headings else 0
            end = len(nodes)
            if headings:
                for i in range(pos+1, len(nodes)):
                    n = nodes[i]
                    if (re.fullmatch('h[1-6]', n.tag)
                            and card_owner(n) is None and article_owner(n) is owner):
                        end = i; break
            # Do not borrow captions/text from adjacent photographs.
            previous_images = [i for i in range(start, pos) if nodes[i].tag == 'img']
            next_images = [i for i in range(pos+1, end) if nodes[i].tag == 'img']
            if previous_images: start = previous_images[-1] + 1
            if next_images: end = next_images[0]
            local_events = [(i, t) for i, t, n in events if start <= i < end
                            and card_owner(n) is None and article_owner(n) is owner]
            # Window around the image, bounded by the active section, not whole page.
            before = ' '.join(t for i, t in local_events if i <= pos)[-2500:]
            after = ' '.join(t for i, t in local_events if i > pos)[:2500]
            local = ' '.join(x for x in (figure.text() if figure else '', before, after) if x)
            scope = 'figure_section' if figure else 'section'
        contexts.append({'headings': heading_texts, 'alt': node.attrs.get('alt', '') or '',
                         'local_text': local[:5000], 'local_truncated': len(local) > 5000,
                         'scope': scope, 'matched_url': matched,
                         'url_match': 'exact' if urldefrag(target_url)[0] == matched else 'normalized'})
    return {'text': text[:max_chars], 'truncated': len(text) > max_chars,
            'incomplete': incomplete, 'access_blocked':access_blocked,
            'text_too_short':len(text)<180, 'target_found': bool(contexts),
            'contexts': contexts[:8], 'contexts_truncated': len(contexts) > 8,
            'page_url': page_url}
