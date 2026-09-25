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

        rec['states'] = []      # per day start: {idx: [crop, planted_day, consecutive_unwatered, fertilized_until_day, yield]}

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
                    stt = {}
                    for y_, row_ in enumerate(tiles):
                        for x_, t_ in enumerate(row_):
                            if isinstance(t_, dict) and t_.get('kind') == 'PLANT':
                                stt[y_ * 10 + x_] = [t_['crop'], t_['planted_day'], t_.get('consecutive_unwatered', 0),
                                                     t_.get('fertilized_until_day', -1), t_.get('yield_units', 0)]
                    rec['states'].append(stt)
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


def fates(agents, crops=('CARROT', 'TOMATO', 'WHEAT', 'STRAWBERRY')):
    """per planting: fate, harvest age / units, water on each age (from next day's consecutive_unwatered == 0),
    fertilized ages (fertilized_until_day), for plantings whose day-start states were recorded."""
    for agent in agents:
        rows = [json.load(open(f)) for f in sorted((OUT / agent).glob('*.json'))]
        rows = [r for r in rows if r.get('states')]
        n = len(rows)
        if not n:
            print(agent, 'no state records'); continue
        print()
        print(f'{agent} ({n} worlds)')
        for crop in crops:
            P = []
            for r in rows:
                st_ = r['states']
                harv = {}
                died = {}
                for kind, day, idx, c, pd, y in r['events']:
                    if c != crop:
                        continue
                    if kind == 'harvest':
                        harv.setdefault((idx, pd), []).append((day, y))
                    elif kind == 'died':
                        died[(idx, pd)] = day
                for kind, day, idx, c, pd, y in r['events']:
                    if kind != 'plant' or c != crop:
                        continue
                    water, fert = [], []
                    for age in range(0, 20):
                        dd = pd + age + 1
                        if dd >= len(st_):
                            break
                        s1 = st_[dd].get(str(idx)) or st_[dd].get(idx)
                        if not s1 or s1[0] != crop or s1[1] != pd:
                            break
                        water.append(1 if s1[2] == 0 else 0)
                        fert.append(1 if s1[3] >= pd + age else 0)
                    h = harv.get((idx, pd), [])
                    P.append(dict(units=sum(y for _, y in h), hn=len(h), hage=(h[-1][0] - pd) if h else None,
                                  died=(died.get((idx, pd)) - pd) if (idx, pd) in died else None, water=water, fert=fert))
            if not P:
                continue
            k = len(P)
            har = [p for p in P if p['hn']]
            dead = [p for p in P if p['died'] is not None and not p['hn']]
            ages = Counter(p['hage'] for p in har)
            upp = sum(p['units'] for p in P) / k
            print(f'  {crop}: {k / n:.1f} plantings/game, units/planting {upp:.2f}; harvested {len(har)} ({len(har) / k:.0%}), '
                  f'died unharvested {len(dead)} ({len(dead) / k:.0%}) at ages {dict(Counter(p["died"] for p in dead))}, '
                  f'other {k - len(har) - len(dead)}')
            print(f'     harvest ages {dict(sorted(ages.items()))}; units by harvest age '
                  f'{ {a: round(st.mean(p["units"] for p in har if p["hage"] == a), 2) for a in sorted(ages)} }')
            for age in range(0, 12):
                w = [p['water'][age] for p in P if len(p['water']) > age]
                f = [p['fert'][age] for p in P if len(p['fert']) > age]
                if w:
                    print(f'     age {age:2d}: alive-next-day {len(w):4d}  watered {sum(w) / len(w):5.0%}  fertilized {sum(f) / len(f):5.0%}')


def main():
    if sys.argv[1] == 'fates':
        fates(sys.argv[2].split(','))
        return
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
