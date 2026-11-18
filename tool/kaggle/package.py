#!/usr/bin/env python3
"""Allowlisted upload archive. Never includes secrets, pilot outputs or caches."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['approve_tool.py', 'matching.py', 'source_page.py', 'name_overrides.json', 'pilot_v1_selection.json',
         'kaggle/run_gpu.py', 'kaggle/gpu_backend.py', 'kaggle/qwen_policy.py', 'kaggle/requirements.txt',
         'kaggle/README.md', 'kaggle/approve_images.ipynb', 'kaggle/restore.py']


def build(root=ROOT):
    archive = root/'tool_kaggle_bundle.zip'
    names = FILES+['input/general_10m_part_02_copy.csv']
    missing = [name for name in names if not (root/name).is_file()]
    if missing: raise SystemExit('Missing: '+', '.join(missing))
    temp = archive.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        for name in names: z.write(root/name, 'tool/'+name)
    temp.replace(archive)
    info = {'file': archive.name, 'bytes': archive.stat().st_size,
            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': ['tool/'+n for n in names]}
    (root/'kaggle/package_manifest.json').write_text(json.dumps(info, indent=2)+'\n')
    print(f'{archive} ({info["bytes"]/1024**2:.1f} MiB)')
    return archive


if __name__ == '__main__': build()
