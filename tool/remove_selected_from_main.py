#!/usr/bin/env python3
"""Remove selected records from the main CSV, ignoring their reviewed approve label."""
import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from approve_tool import ROOT, read_csv, export_csv, digest, atomic_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main', type=Path, default=ROOT.parent / 'general_10m_part_02.csv')
    parser.add_argument('--selected', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    source, selected = args.main.resolve(), args.selected.resolve()
    # A reviewed done CSV is a read-only reference; only the main CSV may be written.
    if source == selected or 'done' in source.parts:
        raise ValueError('Invalid input paths')
    raw, selected_raw = source.read_bytes(), selected.read_bytes()
    rows, fields, _, enc, nl, sha = read_csv(source)
    chosen, chosen_fields, *_ = read_csv(selected)
    assert sha == digest(raw) and fields == chosen_fields
    match_fields = [field for field in fields if field != 'approve']
    def key(row):
        return tuple(row[field] for field in match_fields)
    target_counts = Counter(key(row) for row in chosen)
    main_counts = Counter(key(row) for row in rows)
    missing = target_counts - main_counts
    if missing:
        raise ValueError(f'{sum(missing.values())} selected record occurrences missing from main; inspect before applying')
    remaining, removed = [], []
    for row in rows:
        (removed if key(row) in target_counts else remaining).append(row)
    assert not ({key(row) for row in remaining} & target_counts.keys())
    assert len(rows) == len(remaining) + len(removed)
    assert Counter(tuple(row[f] for f in fields) for row in rows) == (
        Counter(tuple(row[f] for f in fields) for row in remaining)
        + Counter(tuple(row[f] for f in fields) for row in removed))
    stamp = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%Y%m%d_%H%M%S_%f')
    report = {'main': str(source), 'selected': str(selected), 'applied': False,
              'main_sha_before': sha, 'selected_sha': digest(selected_raw),
              'before_rows': len(rows), 'selected_rows': len(chosen),
              'selected_unique_keys': len(target_counts), 'removed_rows': len(removed),
              'extra_duplicate_occurrences_removed': len(removed) - len(chosen),
              'remaining_rows': len(remaining), 'remaining_overlap': 0,
              'match_fields': match_fields}
    if args.apply:
        backup = ROOT / 'backups' / f'{source.stem}_before_remove_selected_{stamp}.csv'
        backup.parent.mkdir(exist_ok=True)
        with backup.open('xb') as f:
            f.write(raw)
        if source.read_bytes() != raw or selected.read_bytes() != selected_raw:
            raise RuntimeError('Input changed externally; not written')
        export_csv(source, remaining, fields, {}, enc, nl)
        check, check_fields, *_ = read_csv(source)
        assert check == remaining and check_fields == fields
        assert not any(key(row) in target_counts for row in check)
        assert selected.read_bytes() == selected_raw
        report.update(applied=True, backup=str(backup), main_sha_after=digest(source.read_bytes()))
        audit = ROOT / 'outputs' / 'main_removals' / f'remove_from_main_{stamp}.json'
        atomic_json(audit, report)
        print(audit)
    import json
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
