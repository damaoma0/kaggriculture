"""Assemble the multi-file Kaggle agent archive for mgt_v9lite (NOT a submission by itself).

Copy of scripts/package_v9y3.py: main.py is scripts/package_v9lite_main.py and the lite module is added.

  package_v9lite.py <out_dir>        -> <out_dir>/pkg/ (the unpacked agent) and <out_dir>/submission.tar.gz

Contents (the dependency closure traced by scripts/trace_agent_files.py on a full game):
  main.py                        scripts/package_v9lite_main.py
  agents/mgt_y3.py               the packaged y3 (submissions/2026-09-24-mgt_y3/main.py, byte for byte)
  agents/mgt_m1.py               read by value_tape_search at import (default clone source, then replaced by y3)
  scripts/<14 modules>           the V9 chain, unchanged, plus value_tape_search_lite
  data/kaggriculture.py          engine copy read by cumulative_engine_profiles (identical to engine 1.32.7)
  results/fresh/value_tape_followup_20260923/{rival_library,modern_rival_library}/   the opponent libraries
"""
import hashlib, json, shutil, sys, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ['value_tape_search', 'value_tape_search_v2', 'value_tape_search_v3', 'value_tape_search_v5',
           'value_tape_search_v6', 'value_tape_search_v7', 'value_tape_search_v8', 'value_tape_search_v9', 'value_tape_search_lite',
           'rival_trajectory_model', 'rival_trajectory_model_v3', 'research_labour_profit',
           'cumulative_engine_profiles', 'test_labour_selfplay']
LIBS = ['results/fresh/value_tape_followup_20260923/rival_library',
        'results/fresh/value_tape_followup_20260923/modern_rival_library']


def main():
    out = Path(sys.argv[1]).resolve()
    pkg = out / 'pkg'
    shutil.rmtree(pkg, ignore_errors=True)
    (pkg / 'scripts').mkdir(parents=True)
    (pkg / 'agents').mkdir()
    (pkg / 'data').mkdir()
    shutil.copy(ROOT / 'scripts/package_v9lite_main.py', pkg / 'main.py')
    shutil.copy(ROOT / 'submissions/2026-09-24-mgt_y3/main.py', pkg / 'agents/mgt_y3.py')
    shutil.copy(ROOT / 'agents/mgt_m1.py', pkg / 'agents/mgt_m1.py')
    for m in MODULES:
        shutil.copy(ROOT / 'scripts' / f'{m}.py', pkg / 'scripts' / f'{m}.py')
    shutil.copy(ROOT / 'data/kaggriculture.py', pkg / 'data/kaggriculture.py')
    for lib in LIBS:
        dst = pkg / lib
        dst.mkdir(parents=True)
        for f in (ROOT / lib).iterdir():
            if f.name == 'manifest.json' or f.name.endswith('.json.gz'):
                shutil.copy(f, dst / f.name)
    files = sorted(p for p in pkg.rglob('*') if p.is_file())
    manifest = {p.relative_to(pkg).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    tar = out / 'submission.tar.gz'
    with tarfile.open(tar, 'w:gz') as t:
        for p in files:
            t.add(p, arcname=p.relative_to(pkg).as_posix())
    (out / 'MANIFEST.json').write_text(json.dumps(dict(files=manifest, archive_sha256=hashlib.sha256(tar.read_bytes()).hexdigest(),
                                                       archive_mb=round(tar.stat().st_size / 1e6, 2)), indent=1), encoding='utf-8')
    print(f'{len(files)} files, archive {tar.stat().st_size / 1e6:.2f} MB -> {tar}')


if __name__ == '__main__':
    main()
