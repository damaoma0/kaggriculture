"""Derive a release archive by removing thread-unsafe global output redirection.

Keeps the qualified source artifact intact. No policy/search operation changes.
"""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'submissions/2026-09-24-v9lite-candidate-01a0'
OUT = ROOT / 'submissions/2026-09-24-v9lite-iofix-01a0'

def digest(path):
    return sha256(path.read_bytes()).hexdigest()

def main():
    old = json.loads((BASE / 'MANIFEST.json').read_text())
    assert digest(BASE / 'submission.tar.gz') == old['archive_sha256']
    assert not OUT.exists(), 'Never overwrite a release artifact'
    for name, wanted in old['files'].items():
        assert digest(BASE / 'pkg' / name) == wanted
    shutil.copytree(BASE / 'pkg', OUT / 'pkg', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    target = OUT / 'pkg/scripts/research_labour_profit.py'
    source = target.read_text(encoding='utf-8')
    marker = 'with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):'
    assert source.count(marker) == 2
    source = source.replace('from contextlib import redirect_stdout, redirect_stderr', 'from contextlib import nullcontext')
    source = source.replace(marker, 'with nullcontext():  # No process-global streams: background forecasts may overlap loader capture.')
    target.write_text(source, encoding='utf-8', newline='\n')
    files = {p.relative_to(OUT / 'pkg').as_posix(): digest(p)
             for p in sorted((OUT / 'pkg').rglob('*')) if p.is_file()}
    assert set(files) == set(old['files'])
    changed = [name for name in files if files[name] != old['files'][name]]
    assert changed == ['scripts/research_labour_profit.py'], changed
    archive = OUT / 'submission.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for name in files:
            tar.add(OUT / 'pkg' / name, arcname=name)
    manifest = dict(files=files, archive_sha256=digest(archive),
        parent_archive_sha256=old['archive_sha256'], changed_files=changed,
        purpose='Remove both process-global output redirect contexts from engine import and simulator initialization; fixes background warm-up versus official-loader capture race. All engine calls and policy/search bytes preserved.')
    (OUT / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k:v for k,v in manifest.items() if k != 'files'}, indent=2))

if __name__ == '__main__':
    main()
