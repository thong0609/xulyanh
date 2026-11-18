#!/usr/bin/env python3
"""Apply an audited set of same-image entity aliases to an unchanged CSV snapshot."""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from approve_tool import ROOT, read_csv, export_csv, atomic_json, digest
from image_quality import protected_image_urls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    review = json.loads(args.review.read_text())
    source = Path(review['source']).resolve()
    if not source.is_relative_to(ROOT / 'outputs'):
        raise ValueError('Source must be under tool/outputs')
    raw = source.read_bytes()
    rows, fields, ids, enc, nl, sha = read_csv(source)
    if digest(raw) != sha or sha != review['source_sha']:
        raise ValueError('CSV changed since alias review; review again before applying')
    updated = [dict(r) for r in rows]
    blocked = protected_image_urls(source)
    changes = []
    seen = set()
    for item in review['pairs']:
        i, j = item['data_row'] - 1, item['anchor_data_row'] - 1
        if i == j or i in seen:
            raise ValueError('Duplicate or self-linked target')
        seen.add(i)
        r, anchor = rows[i], rows[j]
        if r['image_url'] in blocked:
            raise ValueError('Ảnh bị quality reject/review: không được mở rộng yes')
        if not r['image_url'].strip() or r['image_url'] != anchor['image_url']:
            raise ValueError('Different image group')
        if anchor['approve'].strip().lower() != 'yes':
            raise ValueError('Anchor is not an original yes')
        if (r['entity_name'], anchor['entity_name']) != (item['entity_name'], item['anchor_entity_name']):
            raise ValueError('Names changed')
        if r['approve'].strip().lower() == 'yes':
            raise ValueError('Target is already yes')
        updated[i]['approve'] = 'yes'
        changes.append({**item, 'row_id': ids[i], 'before': r['approve'],
                        'after': 'yes', 'image_url': r['image_url']})
    stamp = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%Y%m%d_%H%M%S_%f')
    audit = source.parent / f'reviewed_aliases_{stamp}'
    audit.mkdir()
    if changes:
        with (audit / 'changes.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(changes[0]))
            writer.writeheader()
            writer.writerows(changes)
    report = {'source': str(source), 'source_sha_before': sha, 'applied': False,
              'changes': len(changes), 'groups_changed': len({c['image_url'] for c in changes}),
              'before_counts': dict(Counter(r['approve'] or 'blank' for r in rows)),
              'after_counts': dict(Counter(r['approve'] or 'blank' for r in updated)),
              'review': str(args.review.resolve())}
    if args.apply and changes:
        backup = source.parent / 'backups' / f'selected_rows_before_reviewed_aliases_{stamp}.csv'
        backup.parent.mkdir(exist_ok=True)
        with backup.open('xb') as f:
            f.write(raw)
        if source.read_bytes() != raw:
            raise RuntimeError('CSV changed externally; not written')
        export_csv(source, updated, fields, {}, enc, nl)
        check, check_fields, *_ = read_csv(source)
        assert check == updated and check_fields == fields
        for i, (before, after) in enumerate(zip(rows, check)):
            assert all(before[k] == after[k] for k in fields if k != 'approve')
            if i not in seen:
                assert before == after
        report.update(applied=True, backup=str(backup), source_sha_after=digest(source.read_bytes()))
    atomic_json(audit / 'report.json', report)
    print(json.dumps(report, ensure_ascii=False))
    print(audit)


if __name__ == '__main__':
    main()
