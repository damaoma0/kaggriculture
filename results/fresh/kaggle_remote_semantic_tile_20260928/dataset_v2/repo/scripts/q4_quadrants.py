"""Per-QUADRANT economics, ordinal by purchase order (first = NW start quadrant, second = first purchase $1,000,
third = second purchase $2,000, fourth = third purchase $4,000), for our builds (lead_cycles records) and for the
3000+ leaders (data/leader_semantics).

usage: q4_quadrants.py ours <agent>[,<agent>...] [--dir results/fresh/lead_cycles]
       q4_quadrants.py leaders [--episodes e1,TEAM:e2,...] [--teams DSM,DECEM,...]
       q4_quadrants.py hires <agentA> <agentB>

Ours: from the day-start boards / plant+harvest events / animal harvest events / labour account of lead_cycles records.
  held tile-days = 25 x days from the first day-start board on which the quadrant is unlocked; crop / animal / empty
  tile-days from day-start boards; plantings, harvested units (exact per tile); income attributed = harvested units x
  our realised average sale price of the product in that game (unsold units included at that price); WATER / FERTILIZE
  commands per crop tile-day, FEED / CARE / COLLECT_FERTILIZER per animal tile-day (unit commands at the unit's tile,
  effective or not; no-effect commands are ~0 in this executor); deaths (plant -> weed); labour = unit-steps (tile ops +
  the walking charged to them); dropped = maintenance value left undone at 23h (idle trace, module coins).
Leaders: same quantities from the corpus; harvested units per quadrant by the equal-share split of each day's units of
  a product over that day's harvested tiles of that product (an assumption: exact when one quadrant did all of that
  product's harvests that day); maintenance counts are commands that took effect; deaths are not in the corpus.
"""
import gzip
import glob
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_OF = {'GOOSE': 'EGG', 'COW': 'MILK', 'SHEEP': 'WOOL'}
CROP_LAB = {'WH': 'WHEAT', 'CA': 'CARROT', 'TO': 'TOMATO', 'ST': 'STRAWBERRY', 'ME': 'MELON'}
ANIM_LAB = {'go': 'EGG', 'co': 'MILK', 'sh': 'WOOL'}
NAMES = {'16915014': 'Boey', '16623559': 'DECEM', '16681125': 'MMPQ', '16730612': 'MG', '16770421': 'Vadim',
         '16732748': 'DSM'}
ORD = ('first', 'second', 'third', 'fourth')
FIB = [1, 1]
while len(FIB) < 30:
    FIB.append(FIB[-1] + FIB[-2])


def quad(i):
    i = int(i)
    return ('N' if i // 10 < 5 else 'S') + ('W' if i % 10 < 5 else 'E')


QTILES = {q: [i for i in range(100) if quad(i) == q] for q in ('NW', 'NE', 'SW', 'SE')}


def labs(b):
    if isinstance(b, list) and b and len(b[0]) == 2:
        return b
    s = ''.join(b)
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def unlock_days(boards):
    out = {'NW': 0}
    for d, L in enumerate(boards):
        for q in ('NE', 'SW', 'SE'):
            if q not in out and all(L[i] != ' L' for i in QTILES[q]):
                out[q] = d
    return out


def ordinals(ud):
    """quadrant -> ordinal by unlock day (NW first; ties by the engine's order NE, SW, SE)."""
    rank = {'NW': 0, 'NE': 1, 'SW': 2, 'SE': 3}
    qs = sorted(ud, key=lambda q: (ud[q], rank[q]))
    return {q: ORD[k] for k, q in enumerate(qs)}


def ours(agents, ddir):
    for agent in agents:
        files = sorted((ddir / agent).glob('*.json'))
        rows = [json.loads(f.read_text(encoding='utf-8')) for f in files]
        rows = [r for r in rows if r.get('boards')]
        n = len(rows)
        acc = defaultdict(Counter)
        buy = defaultdict(list)
        qname = defaultdict(Counter)
        for r, f in zip(rows, [f for f in files if json.loads(f.read_text(encoding='utf-8')).get('boards')]):
            B = [labs(b) for b in r['boards']]
            ud = unlock_days(B)
            od = ordinals(ud)
            price = {p: r['panel']['revenue'][p] / r['panel']['sold'][p] for p in r['panel']['sold'] if r['panel']['sold'][p]}
            for q, o in od.items():
                buy[o].append(ud[q] - 1 if q != 'NW' else 0)
                qname[o][q] += 1
                a = acc[o]
                for d in range(ud[q], len(B)):
                    for i in QTILES[q]:
                        l = B[d][i]
                        a['held'] += 1
                        if l in CROP_LAB:
                            a['crop_td'] += 1
                            a['td_' + CROP_LAB[l]] += 1
                        elif l in ANIM_LAB:
                            a['anim_td'] += 1
                        elif l in (' .', 'we'):
                            a['empty_td'] += 1
                        else:
                            a['struct_td'] += 1
            for kind, day, idx, crop, pd, y in r['events']:
                o = od.get(quad(idx))
                if o is None:
                    continue
                if kind == 'plant':
                    acc[o]['plant_' + crop] += 1
                elif kind == 'harvest':
                    acc[o]['units_' + crop] += y
                    acc[o]['inc_crop'] += y * price.get(crop, 0)
                elif kind == 'died':
                    acc[o]['died_' + crop] += 1
            for day, idx, an, u in r.get('aevents', []):
                o = od[quad(idx)]
                p = PRODUCT_OF[an]
                acc[o]['units_' + p] += u
                acc[o]['inc_anim'] += u * price.get(p, 0)
            for dw in r.get('work', []):
                for q, o in od.items():
                    for k, v in dw.get(q, {}).items():
                        acc[o][k] += v
            idir = ddir / agent / 'idle' / f.stem
            for g in idir.glob('*.jsonl') if idir.exists() else []:
                for line in open(g, encoding='utf-8'):
                    for j in json.loads(line).get('dropped', []):
                        acc[od.get(quad(j['idx']), 'first')]['dropped'] += j['value']
        print(f'\n== {agent} ({n} worlds), per game, by quadrant ordinal (quadrant names seen)')
        hdr = ['bought day', 'held tile-days', 'crop / animal / empty tile-days', 'plantings', 'harvested units',
               'income attributed', 'crop income / crop tile-day', 'animal income / animal tile-day', 'income / held tile-day',
               'WATER / crop tile-day', 'FERTILIZE / crop tile-day', 'FEED, CARE / animal tile-day', 'plants died',
               'labour unit-steps (ops + walk)', 'unit-steps / held tile-day', 'dropped maintenance (coins)']
        for o in ORD:
            a = acc[o]
            if not buy[o]:
                continue
            m = lambda k: a[k] / n
            print(f'  {o.upper()} {dict(qname[o])}: bought day {st.mean(buy[o]):.1f}; held {m("held"):.0f} tile-days; '
                  f'crop {m("crop_td"):.0f} / animal {m("anim_td"):.0f} / empty+weed {m("empty_td"):.0f} / empty structure {m("struct_td"):.0f}')
            print('     crop tile-days ' + ', '.join(f'{c.lower()} {m("td_" + c):.0f}' for c in CROP_LAB.values() if a['td_' + c]))
            print('     plantings ' + ', '.join(f'{c.lower()} {m("plant_" + c):.1f}' for c in CROP_LAB.values() if a['plant_' + c])
                  + ' | died ' + ', '.join(f'{c.lower()} {m("died_" + c):.1f}' for c in CROP_LAB.values() if a['died_' + c]))
            print('     harvested ' + ', '.join(f'{p.lower()} {m("units_" + p):.1f}' for p in list(CROP_LAB.values()) + ['EGG', 'MILK', 'WOOL'] if a['units_' + p]))
            ops = sum(v for k, v in a.items() if k.startswith('op_'))
            print(f'     income: crops {m("inc_crop"):,.0f} ({a["inc_crop"] / max(1, a["crop_td"]):.1f} per crop tile-day), animals {m("inc_anim"):,.0f} '
                  f'({a["inc_anim"] / max(1, a["anim_td"]):.1f} per animal tile-day); total per held tile-day {(a["inc_crop"] + a["inc_anim"]) / max(1, a["held"]):.1f}')
            print(f'     WATER {a["op_WATER"] / max(1, a["crop_td"]):.2f}, FERTILIZE {a["op_FERTILIZE"] / max(1, a["crop_td"]):.3f}, HARVEST {a["op_HARVEST"] / max(1, a["crop_td"] + a["anim_td"]):.3f} per crop(+animal) tile-day; '
                  f'FEED {a["op_FEED"] / max(1, a["anim_td"]):.2f}, CARE {a["op_CARE"] / max(1, a["anim_td"]):.2f}, COLLECT_FERT {a["op_COLLECT_FERTILIZER"] / max(1, a["anim_td"]):.2f} per animal tile-day')
            print(f'     labour {(ops + a["walk"]) / n:.0f} unit-steps (ops {ops / n:.0f}, walk {a["walk"] / n:.0f}) = {(ops + a["walk"]) / max(1, a["held"]):.2f} per held tile-day; '
                  f'dropped maintenance {m("dropped"):,.0f} coins')


def leaders(episodes=None, teams=None):
    acc = defaultdict(Counter)
    buy = defaultdict(list)
    qname = defaultdict(Counter)
    n = 0
    for f in sorted(glob.glob(str(ROOT / 'data/leader_semantics/*/*.json.gz'))):
        team = NAMES[Path(f).parent.name]
        ep = Path(f).name.split('.')[0]
        if episodes and ep not in episodes and f'{team}:{ep}' not in episodes:
            continue
        if teams and team not in teams:
            continue
        g = json.load(gzip.open(f, 'rt', encoding='utf-8'))
        n += 1
        days = g['days']
        B = [labs(d['board']) for d in days]
        ud = unlock_days(B)
        od = ordinals(ud)
        su, sr = Counter(), Counter()
        for d in days:
            su.update(d['market']['sold_units'])
            sr.update(d['market']['sold_revenue'])
        price = {p: sr[p] / su[p] for p in su if su[p]}
        for q, o in od.items():
            buy[o].append(ud[q] - 1 if q != 'NW' else 0)
            qname[o][q] += 1
            a = acc[o]
            for d in range(ud[q], 30):
                for i in QTILES[q]:
                    l = B[d][i]
                    a['held'] += 1
                    if l in CROP_LAB:
                        a['crop_td'] += 1
                        a['td_' + CROP_LAB[l]] += 1
                    elif l in ANIM_LAB:
                        a['anim_td'] += 1
                    elif l == ' .':
                        a['empty_td'] += 1
                    else:
                        a['struct_td'] += 1
        for d, day in enumerate(days):
            for crop, tl in day['planted'].items():
                for i in tl:
                    acc[od[quad(i)]]['plant_' + crop] += 1
            for op, tl in (day.get('maintenance') or {}).items():
                for i in tl:
                    acc[od[quad(i)]]['op_' + op] += 1
            h = day.get('harvested') or {}
            byp = defaultdict(list)
            for i in h.get('tiles', []):
                l = B[d][i]
                p = CROP_LAB.get(l) or ANIM_LAB.get(l)
                if p:
                    byp[p].append(i)
                    acc[od[quad(i)]]['op_HARVEST'] += 1
            for p, u in (h.get('units') or {}).items():
                ts = byp.get(p, [])
                for i in ts:
                    o = od[quad(i)]
                    acc[o]['units_' + p] += u / len(ts)
                    acc[o]['inc_crop' if p in CROP_LAB.values() else 'inc_anim'] += u / len(ts) * price.get(p, 0)
    print(f'\n== leaders ({n} games' + (f', teams {teams}' if teams else '') + (f', {len(episodes)} listed episodes' if episodes else '') + '), per game')
    for o in ORD:
        a = acc[o]
        if not buy[o]:
            continue
        k = len(buy[o])
        m = lambda key: a[key] / k
        print(f'  {o.upper()} {dict(qname[o])} (held in {k} games): bought day {st.mean(buy[o]):.1f}; held {m("held"):.0f} tile-days; '
              f'crop {m("crop_td"):.0f} / animal {m("anim_td"):.0f} / empty {m("empty_td"):.0f} / other {m("struct_td"):.0f}')
        print('     crop tile-days ' + ', '.join(f'{c.lower()} {m("td_" + c):.0f}' for c in CROP_LAB.values() if a['td_' + c]))
        print('     plantings ' + ', '.join(f'{c.lower()} {m("plant_" + c):.1f}' for c in CROP_LAB.values() if a['plant_' + c]))
        print('     harvested ' + ', '.join(f'{p.lower()} {m("units_" + p):.1f}' for p in list(CROP_LAB.values()) + ['EGG', 'MILK', 'WOOL'] if a['units_' + p]))
        print(f'     income: crops {m("inc_crop"):,.0f} ({a["inc_crop"] / max(1, a["crop_td"]):.1f} per crop tile-day), animals {m("inc_anim"):,.0f} '
              f'({a["inc_anim"] / max(1, a["anim_td"]):.1f} per animal tile-day); total per held tile-day {(a["inc_crop"] + a["inc_anim"]) / max(1, a["held"]):.1f}')
        print(f'     WATER {a["op_WATER"] / max(1, a["crop_td"]):.2f}, FERTILIZE {a["op_FERTILIZE"] / max(1, a["crop_td"]):.3f}, HARVEST {a["op_HARVEST"] / max(1, a["crop_td"] + a["anim_td"]):.3f} per crop(+animal) tile-day; '
              f'FEED {a["op_FEED"] / max(1, a["anim_td"]):.2f}, CARE {a["op_CARE"] / max(1, a["anim_td"]):.2f} per animal tile-day (took effect)')


def hires(A, B, ddir):
    ra = {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in sorted((ddir / A).glob('*.json'))}
    rb = {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in sorted((ddir / B).glob('*.json'))}
    eps = sorted(e for e in set(ra) & set(rb) if ra[e].get('hands') and rb[e].get('hands'))
    n = len(eps)
    print(f'{A} vs {B}: hands present per day (max over the day), mean of {n} worlds; implied wage = sum fib(0..h-1)')
    print('day  ' + ' '.join(f'{d:5d}' for d in range(30)))
    for lab_, R in ((A, ra), (B, rb)):
        print(f'{lab_[-6:]:5s}' + ' '.join(f'{st.mean(R[e]["hands"][d] for e in eps):5.1f}' for d in range(30)))
    print('delta' + ' '.join(f'{st.mean(ra[e]["hands"][d] - rb[e]["hands"][d] for e in eps):+5.1f}' for d in range(30)))
    idx = Counter()
    extra_wage = 0.0
    for e in eps:
        for d in range(30):
            h1, h0 = ra[e]['hands'][d], rb[e]['hands'][d]
            for k in range(min(h0, h1), max(h0, h1)):
                idx[(k + 1) * (1 if h1 > h0 else -1)] += 1
                extra_wage += FIB[k] * (1 if h1 > h0 else -1)
    print('extra hand-days by hire index (+ = with-SE hired it, - = baseline only), per game: '
          + ', '.join(f'hand #{abs(k)}{"" if k > 0 else " (baseline only)"}: {v / n:.2f} (fib {FIB[abs(k) - 1]})' for k, v in sorted(idx.items(), key=lambda kv: (kv[0] < 0, abs(kv[0])))))
    print(f'implied extra wage per game {extra_wage / n:,.0f}; panel HIRE spend delta '
          f'{st.mean(ra[e]["panel"]["spend"].get("HIRE", 0) - rb[e]["panel"]["spend"].get("HIRE", 0) for e in eps):,.0f}')
    for lab_, R in ((A, ra), (B, rb)):
        imp = st.mean(sum(sum(FIB[:h]) for h in R[e]['hands']) for e in eps)
        print(f'  {lab_}: implied wages {imp:,.0f} vs panel HIRE {st.mean(R[e]["panel"]["spend"].get("HIRE", 0) for e in eps):,.0f}')


def main():
    a = sys.argv[1:]
    ddir = ROOT / (a[a.index('--dir') + 1] if '--dir' in a else 'results/fresh/lead_cycles')
    if a[0] == 'ours':
        ours(a[1].split(','), ddir)
    elif a[0] == 'leaders':
        eps = set(a[a.index('--episodes') + 1].split(',')) if '--episodes' in a else None
        teams = set(a[a.index('--teams') + 1].split(',')) if '--teams' in a else None
        leaders(eps, teams)
    elif a[0] == 'hires':
        hires(a[1], a[2], ddir)


if __name__ == '__main__':
    main()
