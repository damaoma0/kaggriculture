"""Crop cycles of an agent in ladder-panel worlds, from its own observations (no engine hooks): per tile the plantings,
harvests (units, crop age), deaths, and day-start crop counts. Then per crop: plantings, harvested units, units per
planting, harvest age vs full-yield age, cycle length per tile (planting -> next planting on the same tile), tile-days.

usage: lead_cycles.py run <agent> <episodes|smoke> [submission=p2750]    -> results/fresh/lead_cycles/<agent>/<ep>.json
       lead_cycles.py report <agent>[,<agent>...]
"""
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/lead_cycles'
MAXDAY = {'WHEAT': 4, 'CARROT': 3, 'MELON': 10, 'TOMATO': 8, 'STRAWBERRY': 10}   # full-yield age (melon: 6 at age 10)
ONETIME = {'WHEAT', 'CARROT', 'MELON'}


def run(agent, eps, sub):
    import kaggle_environments.agent as KA
    import ladder_panel as LP
    orig = KA.get_last_callable
    for ep in eps:
        path = ROOT / f'data/ladder_panel/{sub}/{ep}.json.gz'
        rec = dict(events=[], counts=[])
        prev = {}

        def snap(t):
            if not isinstance(t, dict) or t.get('kind') != 'PLANT':
                return ('WEED',) if isinstance(t, dict) and t.get('kind') == 'WEED' else None
            return ('PLANT', t['crop'], t['planted_day'], t.get('yield_units', 0))

        def make(entry):
            def wrapped(obs, *a, **k):
                step = int(obs['step'])
                me = int(obs['player'])
                tiles = obs['farms'][me]['tiles']
                cur = {}
                for y, row in enumerate(tiles):
                    for x, t in enumerate(row):
                        cur[y * 10 + x] = snap(t)
                if step % 24 == 0:
                    rec['counts'].append(dict(Counter(v[1] for v in cur.values() if v and v[0] == 'PLANT')))
                if prev:
                    day = (step - 1) // 24
                    for idx, v in cur.items():
                        p = prev.get(idx)
                        if v and v[0] == 'PLANT' and (not p or p[0] != 'PLANT' or p[2] != v[2] or p[1] != v[1]):
                            rec['events'].append(('plant', day, idx, v[1], v[2], 0))
                        if p and p[0] == 'PLANT':
                            crop, pd, y0 = p[1], p[2], p[3]
                            if v is None and y0 > 0:
                                rec['events'].append(('harvest', day, idx, crop, pd, y0))
                            elif v and v[0] == 'PLANT' and v[2] == pd and v[3] == 0 and y0 > 0:
                                rec['events'].append(('harvest', day, idx, crop, pd, y0))
                            elif v and v[0] == 'WEED':
                                rec['events'].append(('died', day, idx, crop, pd, y0))
                prev.clear()
                prev.update(cur)
                return entry(obs, *a, **k)
            return wrapped

        def patched(raw, path=None):
            return make(orig(raw, path=path))
        KA.get_last_callable = patched
        try:
            r = LP.run((agent, str(path)))
        finally:
            KA.get_last_callable = orig
        rec['final'] = r['final']
        rec['margin'] = r['margin']
        rec['sold'] = r['sold']
        o = OUT / agent
        o.mkdir(parents=True, exist_ok=True)
        (o / f'{ep}.json').write_text(json.dumps(rec), encoding='utf-8')
        print(agent, ep, r['margin'], flush=True)


def report(agents):
    for agent in agents:
        rows = [json.load(open(f)) for f in sorted((OUT / agent).glob('*.json'))]
        n = len(rows)
        if not n:
            continue
        plants, units, died = Counter(), Counter(), Counter()
        ages = defaultdict(list)
        cycles = defaultdict(list)
        tdays = Counter()
        for r in rows:
            last = {}
            for kind, day, idx, crop, pd, y in r['events']:
                if kind == 'plant':
                    plants[crop] += 1
                    if idx in last:
                        cycles[last[idx][1]].append(pd - last[idx][0])
                    last[idx] = (pd, crop)
                elif kind == 'harvest':
                    units[crop] += y
                    if crop in ONETIME:
                        ages[crop].append(day - pd - MAXDAY[crop])
                elif kind == 'died':
                    died[crop] += 1
            for c in r['counts']:
                tdays.update(c)
        print(f'\n{agent} ({n} worlds), per game:')
        print(f'{"crop":11s} {"plantings":>9s} {"harvested":>9s} {"units/plant":>11s} {"harvest age - full-yield age":>28s} {"cycle days":>10s} {"tile-days":>9s} {"died":>5s}')
        for crop in ('WHEAT', 'CARROT', 'STRAWBERRY', 'TOMATO', 'MELON'):
            a = ages[crop]
            cy = cycles[crop]
            upp = units[crop] / max(1, plants[crop])
            print(f'{crop:11s} {plants[crop] / n:9.1f} {units[crop] / n:9.1f} {upp:11.2f} '
                  f'{(st.mean(a) if a else 0):+14.2f} (n={len(a)/n:5.1f}) {(st.mean(cy) if cy else 0):10.2f} '
                  f'{tdays[crop] / n:9.0f} {died[crop] / n:5.1f}')


def main():
    if sys.argv[1] == 'run':
        agent = sys.argv[2]
        sub = sys.argv[4] if len(sys.argv) > 4 else 'p2750'
        if sys.argv[3] == 'smoke':
            eps = sorted(f.stem for f in (ROOT / 'results/fresh/ladder_panel/mgt_lead_deploy_s1').glob('*.json'))
        else:
            eps = sys.argv[3].split(',')
        run(agent, eps, sub)
    else:
        report(sys.argv[2].split(','))


if __name__ == '__main__':
    main()
