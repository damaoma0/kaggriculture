import json, sys
from collections import Counter
from pathlib import Path
for tag in sys.argv[1:]:
    rows = []
    for f in sorted(Path(f'results/fresh/lead_agent_20260924/{tag}').glob('1*.json')):
        r = json.load(open(f))
        D = Counter(); M = A = 0
        for dd in r['days']:
            D.update(dd['died']); c = dd['cmds']
            mv = sum(c.get(k, 0) for k in ('NORTH', 'SOUTH', 'EAST', 'WEST')); M += mv; A += sum(c.values()) - mv
        dp = sum(v for k, v in D.items() if k.startswith('unw')); da = sum(v for k, v in D.items() if k.startswith('esc'))
        rows.append(r['ratio'])
        print(f"{tag:8s} {r['episode']} {r['team']:5s} ratio {r['ratio']:.3f} final {r['final']:.0f} plants_died {dp} animals_lost {da} moves {M} acts {A}")
    print(f'{tag} mean ratio {sum(rows)/len(rows):.3f} n={len(rows)}')
