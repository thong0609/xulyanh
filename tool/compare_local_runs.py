#!/usr/bin/env python3
"""Compare completed local runs and produce CSV + offline HTML; no API calls."""
import argparse
from pathlib import Path
import sys
from approve_tool import ROOT, CheckError, atomic_json
sys.path.insert(0,str(ROOT/'kaggle'))
from compare_runs import compare
from render_comparison import build


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-dir',type=Path,default=ROOT/'outputs/pilot_v2_2')
    p.add_argument('--candidate-dir',type=Path,default=ROOT/'outputs/luna_v2_2_pilot50')
    p.add_argument('--output-dir',type=Path,default=ROOT/'outputs/comparison_v2_2_luna')
    p.add_argument('--baseline-rows',action='store_true',help='So sánh đúng seed baseline với candidate đã mở rộng nhóm ảnh')
    p.add_argument('--input',type=Path,default=ROOT/'input/general_10m_part_02_copy.csv')
    p.add_argument('--left-label',default='GPT-5.4 mini v2.2')
    p.add_argument('--right-label',default='GPT-6 Luna v2.2')
    a=p.parse_args(argv)
    if a.output_dir.resolve() in (a.baseline_dir.resolve(),a.candidate_dir.resolve()):
        raise CheckError('Comparison output must differ from result folders')
    path=compare(a.input,a.baseline_dir,a.candidate_dir,a.output_dir,baseline_rows=a.baseline_rows)
    target=a.output_dir/'comparison.csv'
    path.replace(target)
    # Legacy comparison helper uses provider-specific keys; expose neutral names.
    import json
    summary=json.loads((a.output_dir/'comparison_summary.json').read_text())
    summary['baseline_counts']=summary.pop('openai_counts')
    summary['candidate_counts']=summary.pop('qwen_counts')
    summary.update(baseline_label=a.left_label,candidate_label=a.right_label)
    atomic_json(a.output_dir/'comparison_summary.json',summary)
    build(target,a.left_label,a.right_label,candidate_dir=a.candidate_dir if a.baseline_rows else None,input_csv=a.input)
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (CheckError,OSError) as e:print('LỖI:',e);raise SystemExit(2)
