"""Paired comparison of two arms on the 40-world DSM panel (whatever has finished): margin and own cash deltas, t, better
count, deaths, and bank-stop contamination.
usage: pair40.py ARM_A ARM_B"""
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = ROOT / 'results/fresh/sector_20260925/multi'
a, b = sys.argv[1], sys.argv[2]
eps = [g.split(':')[1] for g in (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()]


def load(arm, ep):
    f = M / arm / f'{ep}.json'
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    m = d['money'].get('30')
    if not m:
        return None
    bad = 'bank stop' in str((d.get('tier_err') or {}).get('last_error', ''))
    deaths = sum(v for dd in d['died'].values() for k, v in dd.items() if k != 'animal_SHEEP')
    return m[0], m[1], bad, deaths


rows = [(e, load(a, e), load(b, e)) for e in eps]
rows = [(e, x, y) for e, x, y in rows if x and y]
if not rows:
    print('nothing paired yet')
    sys.exit()
dm = [(x[0] - x[1]) - (y[0] - y[1]) for e, x, y in rows]
do = [x[0] - y[0] for e, x, y in rows]
n = len(rows)
t = lambda v: st.mean(v) / (st.stdev(v) / n ** 0.5) if n > 1 and st.stdev(v) else 0
print(f'{n} worlds: {a} vs {b}: margin {st.mean(dm):+.0f} (t {t(dm):+.2f}, better {sum(x > 0 for x in dm)}/{n}), '
      f'own {st.mean(do):+.0f} (t {t(do):+.2f}) | mean margin {a} {st.mean(x[0] - x[1] for e, x, y in rows):+.0f}, '
      f'{b} {st.mean(y[0] - y[1] for e, x, y in rows):+.0f} | bank stops {sum(x[2] for e, x, y in rows)}/{sum(y[2] for e, x, y in rows)} '
      f'| non-sheep deaths {sum(x[3] for e, x, y in rows) / n:.1f} / {sum(y[3] for e, x, y in rows) / n:.1f}')
