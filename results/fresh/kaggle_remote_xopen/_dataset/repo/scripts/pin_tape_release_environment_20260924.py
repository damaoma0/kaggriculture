"""Record/check the framework inputs without changing a frozen evaluation."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/coherent_switch_20260924_01a0/release_lite_qualification'

def main():
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        import kaggle_environments as K
        from kaggle_environments.envs.kaggriculture import kaggriculture as E
    package = Path(K.__file__).resolve().parent
    paths = sorted(p for p in package.rglob('*') if p.is_file() and p.suffix in ('.py', '.json'))
    current = dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                   framework_distribution_version=importlib.metadata.version('kaggle-environments'),
                   framework_root=str(package), engine=str(Path(E.__file__).resolve()),
                   files={str(p.relative_to(package)): sha256(p.read_bytes()).hexdigest() for p in paths})
    target = OUT / 'environment_manifest.json'
    if target.exists():
        saved = json.loads(target.read_text())
        assert saved['environment'] == current, 'Evaluation framework/environment changed'
        print(json.dumps(dict(verified=True, files=len(paths), engine_sha256=sha256(Path(E.__file__).read_bytes()).hexdigest())))
    else:
        target.write_text(json.dumps(dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
            note='Recorded after the first evaluation worlds, before inspecting profit outcomes. This pins the observed environment, not a retroactive proof of earlier process imports.',
            environment=current), indent=2))
        print(json.dumps(dict(recorded=True, files=len(paths), framework_root=str(package))))

if __name__ == '__main__':
    main()
