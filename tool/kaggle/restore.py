"""Restore only input + output files, never code or credentials from a checkpoint."""
from pathlib import Path, PurePosixPath
import shutil
import zipfile


def restore(source, work):
    source, work = Path(source), Path(work).resolve()
    def target(name):
        parts = PurePosixPath(name).parts
        if len(parts) < 3 or parts[0] != 'tool' or parts[1] not in ('input', 'outputs'):
            raise ValueError('Unexpected checkpoint member: '+name)
        if any(p in ('.', '..') for p in parts): raise ValueError('Unsafe archive path')
        path = (work/Path(*parts[1:])).resolve()
        if not path.is_relative_to(work): raise ValueError('Unsafe checkpoint path')
        return path
    if source.is_dir():
        # Point to a directory containing tool/ (or directly to that tool/ directory).
        root = source/'tool' if (source/'tool').is_dir() else source
        files = [(p, 'tool/'+p.relative_to(root).as_posix()) for folder in ('input','outputs')
                 for p in (root/folder).rglob('*') if p.is_file()]
        if not files: raise ValueError('No checkpoint files found')
        for p, name in files:
            dest = target(name)
            if dest.exists() and dest.read_bytes() != p.read_bytes():
                raise ValueError('Refusing to overwrite existing file: '+str(dest))
        for p, name in files:
            dest = target(name); dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists(): shutil.copyfile(p, dest)
    else:
        with zipfile.ZipFile(source) as z:
            members = [i for i in z.infolist() if not i.is_dir()]
            for member in members:
                dest = target(member.filename)
                if dest.exists() and dest.read_bytes() != z.read(member):
                    raise ValueError('Refusing to overwrite existing file: '+str(dest))
            for member in members:
                dest = target(member.filename); dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    with z.open(member) as src, dest.open('wb') as dst: shutil.copyfileobj(src,dst)
    return work
