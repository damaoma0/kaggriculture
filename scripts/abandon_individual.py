"""Abandonment research (2026-09-26): the exact keep-alive value of EACH animal an arm (or DSM) abandoned mid-season
('mid' rows of animals.json, escape night >= 12), one animal at a time (abandon_market.keep_counterfactual on a
single row), full care and fed-only, with the online features of the stop day.
usage: abandon_individual.py <side,...> -> results/fresh/abandon_20260926/individual.json + summary by lost nights"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import abandon_market as AM  # noqa: E402

if __name__ == '__main__':
    sides = sys.argv[1].split(',')
    rows = json.loads((AM.OUT / 'animals.json').read_text(encoding='utf-8'))
    out = []
    cache = {}
    for r in rows:
        if r['side'] not in sides or r['who'] != 0 or r['cls'] != 'mid' or r['escape'] < 12:
            continue
        k = (r['side'], r['ep'])
        if k not in cache:
            cache.clear()
            cache[k] = json.loads((AM.RDIR / r['side'] / f"{r['ep']}.json").read_text(encoding='utf-8'))
        R = cache[k]
        f = AM.keep_counterfactual(R, [r], 'full')
        o = AM.keep_counterfactual(R, [r], 'fed_only')
        out.append(dict(r, keep_full=f, keep_fed=o))
    (AM.OUT / 'individual.json').write_text(json.dumps(out), encoding='utf-8')
    for side in sides:
        rs = [x for x in out if x['side'] == side]
        print(f'== {side}: {len(rs)} abandoned animals ({len(rs) / 40:.2f}/world)')
        by = defaultdict(list)
        for x in rs:
            by[(x['kind'], min(x['lost_nights'], 4))].append(x)
        for (kd, ln), v in sorted(by.items()):
            mf = [x['keep_full']['margin'] for x in v]
            mo = [x['keep_fed']['margin'] for x in v]
            of = [x['keep_full']['own'] for x in v]
            print(f"  {kd:5s} lost nights {ln}{'+' if ln == 4 else ' '} n{len(v):4d} | keep full: margin {mean(mf):+6.0f} (keep better {sum(m > 0 for m in mf) / len(v):4.0%}) own {mean(of):+6.0f}"
                  f" | fed only: margin {mean(mo):+6.0f} (better {sum(m > 0 for m in mo) / len(v):4.0%}) | stop day {mean(x['stop'] for x in v):.1f} q0 {mean(x.get('q_prod', 0) for x in v):.0f} wheat {mean(x.get('q_wheat', 0) for x in v):.0f}")
