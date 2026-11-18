#!/usr/bin/env python3
"""Local CSV image review. Python standard library only."""
import argparse
import csv
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

csv.field_size_limit(10_000_000)
ROOT = Path(__file__).resolve().parent


class ReviewStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.lock = threading.Lock()
        raw = self.path.read_bytes()
        self.encoding = 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8'
        self.line_end = '\r\n' if b'\r\n' in raw else '\n'
        with self.path.open(encoding=self.encoding, newline='') as f:
            reader = csv.DictReader(f)
            self.fields = reader.fieldnames
            if not self.fields or not {'entity_name', 'image_url'} <= set(self.fields):
                raise ValueError('CSV phải có entity_name và image_url.')
            if len(set(self.fields)) != len(self.fields):
                raise ValueError('CSV có tên cột trùng nhau.')
            self.rows = list(reader)
        if any(None in row or any(v is None for v in row.values()) for row in self.rows):
            raise ValueError('CSV có dòng thiếu hoặc thừa cột; hãy sửa trước khi duyệt.')
        if 'approve' not in self.fields:
            self.fields.append('approve')
            for row in self.rows:
                row['approve'] = ''
        self.names = [r['entity_name'].casefold() for r in self.rows]
        self.labels = [r.get('leaf_label', '').strip() for r in self.rows]
        categories = Counter(self.labels)
        self.category_names = {name.casefold() for name in categories if name}
        self.categories = [{'name': name, 'count': count}
                           for name, count in sorted(categories.items(), key=lambda item: item[0].casefold())
                           if name]
        self.signature = self.file_signature()
        self.backup = None

    def file_signature(self):
        s = self.path.stat()
        return s.st_mtime_ns, s.st_size, s.st_ino

    def page(self, query, status, page, size, category=''):
        with self.lock:
            counts = {'yes': 0, 'no': 0, 'pending': 0}
            matches = []
            query = query.casefold().strip()
            category = category.casefold().strip()
            exact_category = category in self.category_names
            for i, row in enumerate(self.rows):
                value = row['approve'].strip().lower()
                kind = value if value in ('yes', 'no') else 'pending'
                counts[kind] += 1
                if ((status == 'all' or status == kind) and query in self.names[i]
                        and (self.labels[i].casefold() == category if exact_category
                             else category in self.labels[i].casefold())):
                    matches.append(i)
            pages = max(1, (len(matches) + size - 1) // size)
            page = min(page, pages)
            return {'file': self.path.name, 'total': len(self.rows), 'counts': counts,
                    'matched': len(matches), 'page': page, 'pages': pages,
                    'categories': self.categories,
                    'rows': [dict(self.rows[i], _index=i) for i in matches[(page-1)*size:page*size]]}

    def save(self, index, value):
        return self.save_many([index], value)

    def save_many(self, indices, value):
        if not isinstance(indices, list) or not indices:
            raise ValueError('Hãy chọn ít nhất một dòng.')
        if any(type(index) is not int for index in indices):
            raise ValueError('Dòng CSV không hợp lệ.')
        return self.save_changes({index: value for index in indices})

    def save_page(self, indices, selected):
        if not isinstance(indices, list) or not indices or len(indices) > 100:
            raise ValueError('Trang không hợp lệ.')
        if not isinstance(selected, list):
            raise ValueError('Lựa chọn không hợp lệ.')
        if any(type(index) is not int for index in indices + selected):
            raise ValueError('Dòng CSV không hợp lệ.')
        if len(set(indices)) != len(indices) or not set(selected) <= set(indices):
            raise ValueError('Lựa chọn phải thuộc trang hiện tại.')
        selected = set(selected)
        return self.save_changes({index: 'yes' if index in selected else 'no' for index in indices})

    def save_changes(self, changes):
        with self.lock:
            if self.file_signature() != self.signature:
                raise RuntimeError('CSV đã bị thay đổi bên ngoài. Hãy khởi động lại server để đọc bản mới.')
            if any(type(index) is not int or not 0 <= index < len(self.rows) for index in changes):
                raise ValueError('Dòng CSV không hợp lệ.')
            if any(value not in ('yes', 'no', '') for value in changes.values()):
                raise ValueError('Giá trị approve không hợp lệ.')
            previous = {index: self.rows[index]['approve'] for index, value in changes.items()
                        if self.rows[index]['approve'] != value}
            if not previous:
                return 0
            if self.backup is None:
                # Exclusive creation: never overwrite an existing backup.
                backup = self.path.with_name(self.path.name + '.bak')
                n = 1
                while True:
                    try:
                        with backup.open('xb') as dst, self.path.open('rb') as src:
                            shutil.copyfileobj(src, dst)
                            dst.flush()
                            os.fsync(dst.fileno())
                        break
                    except FileExistsError:
                        backup = self.path.with_name(self.path.name + f'.bak.{n}')
                        n += 1
                self.backup = backup
            temp = None
            try:
                for index in previous:
                    self.rows[index]['approve'] = changes[index]
                with tempfile.NamedTemporaryFile(mode='w', encoding=self.encoding, newline='',
                                                 dir=self.path.parent, prefix='.csv-review-', delete=False) as f:
                    temp = f.name
                    writer = csv.DictWriter(f, fieldnames=self.fields, lineterminator=self.line_end)
                    writer.writeheader()
                    writer.writerows(self.rows)
                    f.flush()
                    os.fsync(f.fileno())
                os.chmod(temp, stat.S_IMODE(self.path.stat().st_mode))
                if self.file_signature() != self.signature:
                    raise RuntimeError('CSV vừa bị thay đổi bên ngoài; không ghi đè. Hãy khởi động lại server.')
                os.replace(temp, self.path)
                self.signature = self.file_signature()
            except Exception:
                for index, old_value in previous.items():
                    self.rows[index]['approve'] = old_value
                raise
            finally:
                if temp and os.path.exists(temp):
                    os.unlink(temp)
            return len(previous)


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, body, content_type='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path in ('/', '/review.html'):
                return self.reply(200, (ROOT / 'review.html').read_bytes(), 'text/html; charset=utf-8')
            if parsed.path != '/api/rows':
                return self.reply(404, {'error': 'Không tìm thấy.'})
            try:
                q = parse_qs(parsed.query)
                page = max(1, int(q.get('page', ['1'])[0]))
                size = min(100, max(1, int(q.get('size', ['20'])[0])))
                status = q.get('status', ['all'])[0]
                if status not in ('all', 'yes', 'no', 'pending'):
                    raise ValueError('Bộ lọc không hợp lệ.')
                self.reply(200, store.page(q.get('q', [''])[0], status, page, size, q.get('category', [''])[0]))
            except ValueError as e:
                self.reply(400, {'error': str(e)})

        def do_POST(self):
            if self.path not in ('/api/approve', '/api/approve-batch', '/api/approve-page'):
                return self.reply(404, {'error': 'Không tìm thấy.'})
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.reply(403, {'error': 'Origin không hợp lệ.'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.reply(415, {'error': 'Yêu cầu JSON.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1_000_000:
                    raise ValueError('Yêu cầu không hợp lệ.')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError('Yêu cầu không hợp lệ.')
                if self.path == '/api/approve-page':
                    changed = store.save_page(payload.get('indices'), payload.get('selected'))
                elif self.path == '/api/approve-batch':
                    changed = store.save_many(payload.get('indices'), payload.get('approve'))
                else:
                    changed = store.save(payload.get('index'), payload.get('approve'))
                self.reply(200, {'ok': True, 'changed': changed})
            except (ValueError, TypeError) as e:
                self.reply(400, {'error': str(e)})
            except RuntimeError as e:
                self.reply(409, {'error': str(e)})
            except OSError:
                self.reply(500, {'error': 'Không ghi được CSV. Kiểm tra quyền ghi và dung lượng ổ đĩa.'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', nargs='?', type=Path)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if args.csv is None:
        candidates = sorted(ROOT.glob('*.csv'))
        if len(candidates) != 1:
            parser.error('Hãy chỉ định file CSV: python3 review_server.py ten_file.csv')
        args.csv = candidates[0]
    store = ReviewStore(args.csv)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(store))
    print(f'CSV: {store.path} ({len(store.rows):,} dòng)', flush=True)
    print(f'Mở http://127.0.0.1:{server.server_port} — Ctrl+C để dừng', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
