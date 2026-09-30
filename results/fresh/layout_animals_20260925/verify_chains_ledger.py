"""Skeptic check of the report's item 4 (ledger comparison): recompute leader / ours / deploy fertilizer flow from
results/fresh/lead_ledger/{leader,ours,deploy}_*.json (stored, engine-hook counts from the lead thread), plus the
reclassification of the reviewed events.jsonl.gz under the 'entered the shed' definition (animal on a shed tile).
Stored data only."""
import glob
import gzip
import json
import os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TEAM = {'16732748': 'DSM', '16770421': 'Vadim', '16730612': 'UMG'}
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))


def dsh(p):
    return min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED)


print('LEDGER (per game means)')
for side in ('leader', 'ours', 'deploy'):
    tot = defaultdict(Counter)
    ng = Counter()
    files = sorted(glob.glob(os.path.join(ROOT, 'results', 'fresh', 'lead_ledger', f'{side}_*.json')))
    for fp in files:
        d = json.load(open(fp, encoding='utf-8'))
        tm = TEAM.get(d['game'].split(':')[0], '?')
        for grp in ('all', tm):
            ng[grp] += 1
            c = tot[grp]
            for dd in d['days']:
                c['collect'] += dd['eff'].get('COLLECT_FERTILIZER', 0)
                c['applied'] += dd['eff'].get('FERTILIZE', 0)
                c['picked'] += dd['picked'].get('FERTILIZER', 0)
                c['deposited'] += dd['deposited'].get('FERTILIZER', 0)
                c['dump'] += (dd.get('carried_mid') or {}).get('FERTILIZER', 0)
                c['sold'] += dd['sold'].get('FERTILIZER', 0)
                c['moves'] += dd['move'] - dd['move_noeff']
                c['feed'] += dd['eff'].get('FEED', 0)
                c['care'] += dd['eff'].get('CARE', 0)
                c['picked_wheat'] += dd['picked'].get('WHEAT', 0)
            c['final'] += d['final']
            c['target'] += d['target']
    for grp in ('all', 'DSM'):
        n = ng[grp]
        c = tot[grp]
        print(f'  {side:6s} {grp:3s} n={n:2d}: picked {c["picked"] / n:6.1f} collect {c["collect"] / n:6.1f} applied '
              f'{c["applied"] / n:6.1f} deposited {c["deposited"] / n:6.1f} dump {c["dump"] / n:6.1f} sold '
              f'{c["sold"] / n:6.1f} moves {c["moves"] / n:6.0f} | FEED {c["feed"] / n:5.0f} CARE {c["care"] / n:5.0f} '
              f'wheat picked {c["picked_wheat"] / n:5.0f} | final {c["final"] / n:8.0f} (leader target {c["target"] / n:8.0f})')

print('\nRECLASSIFICATION of events.jsonl.gz (all seat-games): field-sourced FERTILIZE flagged shed_between whose '
      'animal stands ON a shed tile (dshed 0) -> counted as direct')
tot = Counter()
dA_t, dA_e = [], []
G = 0
with gzip.open(os.path.join(HERE, 'events.jsonl.gz'), 'rt', encoding='utf-8') as f:
    for line in f:
        r = json.loads(line)
        G += 1
        for x in r['fert']:
            tot['n'] += 1
            if x['src'] != 'field':
                continue
            tot['field'] += 1
            a0 = dsh(x['A']) == 0
            if not x['shed_between']:
                tot['direct'] += 1
                dA_t.append(dsh(x['A']))
                dA_e.append(dsh(x['A']))
            else:
                tot['after'] += 1
                if a0:
                    tot['after_dshed0'] += 1
                    dA_e.append(0)
        for c in r['collect']:
            tot['collect'] += 1
            tot['collect_dshed0'] += dsh(c['A']) == 0
n = tot['n']
print(f'  seat-games {G}; FERTILIZE {n}; field {tot["field"]} ({tot["field"] / n:.3f}); direct as reported '
      f'{tot["direct"]} ({tot["direct"] / n:.3f}); flagged after-shed {tot["after"]} ({tot["after"] / n:.3f}) of which '
      f'animal on a shed tile {tot["after_dshed0"]} ({tot["after_dshed0"] / max(1, tot["after"]):.3f} of after-shed)')
print(f'  direct incl. on-shed-tile animals: {tot["direct"] + tot["after_dshed0"]} '
      f'({(tot["direct"] + tot["after_dshed0"]) / n:.3f}); mean animal dshed as reported {sum(dA_t) / len(dA_t):.2f}, '
      f'incl. on-shed-tile animals {sum(dA_e) / len(dA_e):.2f}; share of chain animals at dshed 0: '
      f'{dA_e.count(0) / len(dA_e):.3f}')
print(f'  COLLECTs from animals on a shed tile: {tot["collect_dshed0"]} of {tot["collect"]} '
      f'({tot["collect_dshed0"] / tot["collect"]:.3f})')
