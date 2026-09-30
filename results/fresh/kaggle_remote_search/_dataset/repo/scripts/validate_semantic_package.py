"""Run the archived entry point in an isolated Python process and working directory."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,tarfile,tempfile
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('package');args=parser.parse_args()
    source=(ROOT/args.package).resolve();manifest=json.loads((source/'manifest.json').read_text())
    archive=source/'semantic_farm.tar.gz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['archive_sha256']
    with tempfile.TemporaryDirectory(prefix='semantic-package-') as directory:
        folder=Path(directory)
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                if member.name not in manifest['files'] or not member.isfile():raise ValueError('unexpected_member')
                target=folder/member.name;target.parent.mkdir(parents=True,exist_ok=True)
                data=tar.extractfile(member).read()
                assert hashlib.sha256(data).hexdigest()==manifest['files'][member.name]
                target.write_bytes(data)
        driver=folder/'validate.py'
        driver.write_text('''import sys,json
from pathlib import Path
root=Path(sys.argv[1]);pkg=Path.cwd()
sys.path.insert(0,str(root/'results/fresh/tape_margin_20260924_01a0/payload/vendor'))
from kaggle_environments.agent import get_last_callable
entry=get_last_callable((pkg/'main.py').read_text(),path=str(pkg/'main.py'))
# All policy modules must be supplied by the archive before the harness is loaded.
from semantic_farm.policy import SemanticFarm
from semantic_farm.model import DEFAULT
assert DEFAULT.is_relative_to(pkg)
for name,module in list(sys.modules.items()):
    if name.startswith(('semantic_farm','fragments.')) or name in ('semantic_strategy','cumulative_engine_profiles'):
        assert Path(module.__file__).is_relative_to(pkg),(name,module.__file__)
sys.path.append(str(root/'scripts'))
import run_semantic_farm as harness
original=harness.load_agent
class Wrapped:
    def __call__(self,obs):return entry(obs)
    @property
    def stats(self):return entry.__globals__['_agent'].stats
    @property
    def history(self):return entry.__globals__['_agent'].history
harness.load_agent=lambda name:Wrapped() if name=='semantic_package' else original(name)
result=harness.play(924723,1,'semantic_package','v56')
assert result['completed'] and result['ledger_verified']
result['isolated_package']=True
Path(sys.argv[2]).write_text(json.dumps(result,indent=2))
print(json.dumps({k:result[k] for k in ('completed','cash','margin','stats','seconds','isolated_package')}))
''',encoding='utf8')
        subprocess.run([sys.executable,'-I',str(driver),str(ROOT),str(source/'validation.json')],cwd=folder,check=True)


if __name__=='__main__':main()
