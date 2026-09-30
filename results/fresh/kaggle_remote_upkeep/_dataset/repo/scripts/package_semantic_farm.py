"""Build an isolated, hash-manifested local research package; never submit."""
from pathlib import Path
import argparse,hashlib,json,shutil,tarfile
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args()
    out=Path(args.output).resolve()
    if out.exists():raise ValueError('choose_new_package_directory')
    pkg=out/'pkg';pkg.mkdir(parents=True)
    paths=[*sorted((ROOT/'scripts/semantic_farm').glob('*.py')),
        ROOT/'scripts/semantic_strategy.py',ROOT/'scripts/cumulative_engine_profiles.py',
        ROOT/'scripts/fragments/continuation_executor.py',ROOT/'scripts/fragments/continuation_projection.py',
        ROOT/'scripts/fragments/segment_job_executor_v3.py',ROOT/'data/kaggriculture.py',
        ROOT/'data/semantic_farm/model.json']
    for path in paths:
        target=pkg/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    (pkg/'main.py').write_text('''import sys
from pathlib import Path
_roots=([Path(__file__).resolve().parent] if '__file__' in globals() else [])+[Path('/kaggle_simulations/agent'),Path.cwd()]
_root=next(p for p in _roots if (p/'data/semantic_farm/model.json').exists())
sys.path.insert(0,str(_root/'scripts'))
from semantic_farm.policy import SemanticFarm
_agent=None
def semantic_farm_agent(observation,configuration=None):
    global _agent
    if _agent is None or observation['step']==0: _agent=SemanticFarm()
    return _agent(observation)
''',encoding='utf8')
    files=sorted(p for p in pkg.rglob('*') if p.is_file())
    hashes={p.relative_to(pkg).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    archive=out/'semantic_farm.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for path in files:tar.add(path,arcname=path.relative_to(pkg).as_posix())
    (out/'manifest.json').write_text(json.dumps(dict(files=hashes,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        status='research package; no submission or promotion'),indent=2),encoding='utf8')
    print(json.dumps(dict(files=len(files),archive=str(archive),bytes=archive.stat().st_size)))


if __name__=='__main__':main()
