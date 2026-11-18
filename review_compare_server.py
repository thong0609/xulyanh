#!/usr/bin/env python3
"""Serve a read-only comparison of the first Qwen and Luna review ranges."""
import argparse
import csv
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
QWEN_DEFAULT = Path('/home/tts/Downloads/reviewed (1).csv')
LUNA_INPUT = ROOT / 'tool/input/general_10m_part_02_copy.csv'
LUNA_OUTPUT = ROOT / 'tool/outputs/luna_rows_2001_4000/results.jsonl'
LUNA_FIRST_INDEX = 2000
LUNA_ROW_COUNT = 300


class LunaJournal:
    def __init__(self, path, source_rows):
        self.path = path
        self.source_rows = source_rows
        self.offset = 0
        self.pending = b''
        self.signature = None
        self.results = {}
        self.lock = threading.Lock()

    def snapshot(self):
        with self.lock:
            if not self.path.exists():
                raise FileNotFoundError(f'Không tìm thấy kết quả Luna: {self.path}')
            stat = self.path.stat()
            signature = (stat.st_dev, stat.st_ino)
            if self.signature != signature or stat.st_size < self.offset:
                self.offset = 0
                self.pending = b''
                self.results.clear()
                self.signature = signature
            with self.path.open('rb') as journal:
                journal.seek(self.offset)
                chunk = journal.read()
            self.offset += len(chunk)
            content = self.pending + chunk
            last_newline = content.rfind(b'\n')
            if last_newline < 0:
                self.pending = content
            else:
                complete, self.pending = content[:last_newline + 1], content[last_newline + 1:]
                for line_number, line in enumerate(complete.splitlines(), 1):
                    if not line:
                        continue
                    try:
                        result = json.loads(line)
                    except json.JSONDecodeError as error:
                        raise ValueError(f'JSONL Luna lỗi gần vị trí byte {self.offset - len(self.pending)}: {error}') from error
                    index = result.get('row_index')
                    if type(index) is not int or not LUNA_FIRST_INDEX <= index < LUNA_FIRST_INDEX + LUNA_ROW_COUNT:
                        continue
                    expected = self.source_rows[index - LUNA_FIRST_INDEX]
                    if result.get('entity_name') != expected['entity_name']:
                        raise ValueError(f'Kết quả Luna dòng dữ liệu {index + 1} không khớp CSV nguồn.')
                    self.results[index] = result
            return dict(self.results)


def read_rows(path, start, count):
    with path.open(encoding='utf-8-sig', newline='') as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not {'entity_name', 'image_url'} <= set(reader.fieldnames):
            raise ValueError(f'CSV thiếu cột entity_name hoặc image_url: {path}')
        rows = []
        for index, row in enumerate(reader):
            if start <= index < start + count:
                rows.append(row)
            if index >= start + count - 1:
                break
    return rows


class CompareData:
    def __init__(self, qwen_path):
        self.qwen_path = qwen_path
        self.qwen_rows = read_rows(qwen_path, 0, 1000)
        self.luna_rows = read_rows(LUNA_INPUT, LUNA_FIRST_INDEX, LUNA_ROW_COUNT)
        if len(self.qwen_rows) != 1000:
            raise ValueError(f'File review 1 chỉ có {len(self.qwen_rows)} dòng đầu vào; cần đủ 1.000 dòng.')
        if len(self.luna_rows) != LUNA_ROW_COUNT:
            raise ValueError(f'CSV nguồn Luna chỉ có {len(self.luna_rows)} dòng trong khoảng yêu cầu.')
        self.journal = LunaJournal(LUNA_OUTPUT, self.luna_rows)

    @staticmethod
    def card_data(row, source_row, completed=True, reason=''):
        return {
            'source_row': source_row,
            'entity_name': row.get('entity_name', ''),
            'leaf_label': row.get('leaf_label', ''),
            'image_url': row.get('image_url', ''),
            'page_url': row.get('page_url', ''),
            'mo_ta': row.get('mo_ta', ''),
            'approve': row.get('approve', ''),
            'completed': completed,
            'reason': reason,
        }

    def qwen(self):
        return [self.card_data(row, index + 1) for index, row in enumerate(self.qwen_rows)]

    def luna(self):
        results = self.journal.snapshot()
        rows = []
        for offset, row in enumerate(self.luna_rows):
            index = LUNA_FIRST_INDEX + offset
            result = results.get(index)
            card = self.card_data(
                row,
                index + 1,
                completed=result is not None,
                reason=result.get('reason', '') if result else '',
            )
            if result is not None:
                card['approve'] = result.get('approve', '')
            rows.append(card)
        return rows


def make_handler(data):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, body, content_type='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path in ('/', '/review_compare.html'):
                return self.reply(200, (ROOT / 'review_compare.html').read_bytes(),
                                  'text/html; charset=utf-8')
            if parsed.path != '/api/data':
                return self.reply(404, {'error': 'Không tìm thấy.'})
            source = parse_qs(parsed.query).get('source', [''])[0]
            try:
                if source == 'qwen':
                    rows = data.qwen()
                    description = f'{data.qwen_path.name} · 1.000 dòng đầu · nhãn hiển thị từ file review 1.'
                elif source == 'luna':
                    rows = data.luna()
                    completed = sum(row['completed'] for row in rows)
                    description = f'Luna · dòng dữ liệu 2.001–2.300 · {completed}/300 đã có kết quả.'
                else:
                    return self.reply(400, {'error': 'source phải là qwen hoặc luna.'})
                return self.reply(200, {'description': description, 'rows': rows})
            except (OSError, ValueError, json.JSONDecodeError) as error:
                return self.reply(500, {'error': str(error)})

        def log_message(self, format, *args):
            print(f'[{self.log_date_time_string()}] {format % args}')

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qwen-csv', type=Path, default=QWEN_DEFAULT,
                        help='File review 1; mặc định là reviewed (1).csv trong Downloads.')
    parser.add_argument('--port', type=int, default=8001)
    args = parser.parse_args()
    data = CompareData(args.qwen_csv)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(data))
    print(f'Qwen: {data.qwen_path} (1.000 dòng đầu)', flush=True)
    print(f'Luna: {LUNA_OUTPUT} (dòng dữ liệu 2.001–2.300)', flush=True)
    print(f'Mở http://127.0.0.1:{server.server_port} · chỉ đọc · Ctrl+C để dừng', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
