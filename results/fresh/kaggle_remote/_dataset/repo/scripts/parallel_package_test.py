"""Run K copies of test_package_isolated.py at once (pessimistic concurrency: K games share the machine), each on its
own seeds, and merge their outputs.
usage: parallel_package_test.py <K> <package dir|tar.gz> <opponent.py> <out.json> <seeds per copy> [extra flags]"""
import json, subprocess, sys
from pathlib import Path

k, pkg, opp, out, n = int(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4]), int(sys.argv[5])
extra = sys.argv[6:]
procs = []
for i in range(k):
    part = out.with_name(f'{out.stem}_p{i}.json')
    procs.append((part, subprocess.Popen([sys.executable, 'scripts/test_package_isolated.py', pkg, opp, str(part), str(n),
                                          f'--seed0={i * n}', *extra])))
rows, foreign, rcs = [], set(), []
for part, p in procs:
    rcs.append(p.wait())
    if part.exists():
        d = json.loads(part.read_text(encoding='utf-8'))
        rows += d['games']
        foreign |= set(d['foreign_modules'])
out.write_text(json.dumps(dict(copies=k, returncodes=rcs, games=rows, foreign_modules=sorted(foreign)), indent=1), encoding='utf-8')
print(json.dumps(dict(returncodes=rcs, games=len(rows), foreign=sorted(foreign))))
sys.exit(max(rcs) if rcs else 1)
