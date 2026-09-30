"""THIRD-quadrant diagnosis (third = the second purchase, $2,000; ours SW), from stored lead_cycles records (q4c1) and
the leader corpus. No games are run.

usage: q4_third.py <agent> [--dir results/fresh/lead_cycles] [--quad third|first|second|fourth]

1. idle land by day: the quadrant's tiles at each day start from its first unlocked day, classified as
   crop / animal / empty structure / weed / empty never used since unlock / empty after a harvest / empty after a death
   (plant -> weed -> cleared) / empty after an animal left; plus, for our records, empty tiles on days past the planting
   cutoffs (wheat 25, carrot 26: nothing can be planted for a full harvest after that).
2. crop mix by source: plantings on the quadrant by crop and by planting day window: days <= 11 = the retrieved
   leader plan (incl. its catch-up plantings), day >= 12 = the count model, split into same-day replants (a planting
   on a tile harvested of the same crop that day = the rpc1 rule) and compose plantings. Leaders: <= 11 / >= 12.
3. dropped maintenance by quadrant and op type (idle trace at 23h, module coins) and the executed ops.
4. animals by day on the quadrant (tile counts by species per day start).
"""
import gzip
import glob
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from q4_quadrants import quad, QTILES, labs, unlock_days, ordinals, NAMES, CROP_LAB  # noqa: E402

ANIM = {'go': 'goose', 'co': 'cow', 'sh': 'sheep'}
CUT = {'WHEAT': 25, 'CARROT': 26, 'TOMATO': 18, 'STRAWBERRY': 13, 'MELON': 19}


def classify_ours(r, q):
    """per day start: Counter of states for quadrant q's tiles."""
    B = [labs(b) for b in r['boards']]
    ud = unlock_days(B)[q]
    last = {}                                   # tile -> last event kind before the day start
    ev_by_day = defaultdict(list)
    for kind, day, idx, crop, pd, y in r['events']:
        ev_by_day[day].append((kind, idx))
    out = []
    for d in range(len(B)):
        for kind, idx in ev_by_day.get(d - 1, []):
            last[idx] = kind
        if d < ud:
            out.append(None)
            continue
        c = Counter()
        for i in QTILES[q]:
            l = B[d][i]
            if l in CROP_LAB:
                c['crop'] += 1
            elif l in ANIM:
                c['animal'] += 1
            elif l in ('Co', 'Pa'):
                c['empty structure'] += 1
            elif l == 'we':
                c['weed'] += 1
            elif l == ' .':
                prev = B[d - 1][i] if d > 0 else ' L'
                lk = last.get(i)
                if lk is None and all(B[k][i] in (' .', ' L') for k in range(ud, d + 1)):
                    c['empty: never used since unlock'] += 1
                elif prev in ANIM or prev in ('Co', 'Pa'):
                    c['empty: animal / structure removed'] += 1
                elif lk == 'harvest':
                    c['empty: after harvest'] += 1
                elif lk == 'died' or prev == 'we':
                    c['empty: after death / weed cleared'] += 1
                else:
                    c['empty: other'] += 1
        out.append(c)
    return out, ud


def ours(agent, ddir, which):
    rows = {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in sorted((ddir / agent).glob('*.json'))}
    rows = {e: r for e, r in rows.items() if r.get('boards')}
    n = len(rows)
    per_day = defaultdict(Counter)
    src = defaultdict(Counter)
    anim_day = defaultdict(Counter)
    tdays = Counter()
    ud_list = []
    dropped = Counter()
    ops = Counter()
    for e, r in rows.items():
        B = [labs(b) for b in r['boards']]
        od = ordinals(unlock_days(B))
        q = next(k for k, v in od.items() if v == which)
        cls, ud = classify_ours(r, q)
        ud_list.append(ud)
        for d, c in enumerate(cls):
            if c is not None:
                per_day[d].update(c)
                for k, v in c.items():
                    tdays[k] += v
                    if k.startswith('empty') or k == 'weed':
                        if d > 26:
                            tdays['(empty/weed on days 27-29, past every cutoff)'] += v
        harv_same_day = {(day, idx, crop) for kind, day, idx, crop, pd, y in r['events'] if kind == 'harvest'}
        for kind, day, idx, crop, pd, y in r['events']:
            if kind != 'plant' or quad(idx) != q:
                continue
            if day <= 11:
                src['plan (days <= 11)'][crop] += 1
            elif (day, idx, crop) in harv_same_day:
                src['count model: same-day replant'][crop] += 1
            else:
                src['count model: compose (day >= 12)'][crop] += 1
        for d, b in enumerate(B):
            if d >= ud:
                for i in QTILES[q]:
                    if b[i] in ANIM:
                        anim_day[d][ANIM[b[i]]] += 1
        idir = ddir / agent / 'idle' / e
        for g in (idir.glob('*.jsonl') if idir.exists() else []):
            for line in open(g, encoding='utf-8'):
                rec = json.loads(line)
                for j in rec.get('dropped', []):
                    dropped[(od[quad(j['idx'])], j['cmd'], j.get('kind') or '?')] += j['value']
        for dw in r.get('work', []):
            for qq, o in od.items():
                for k, v in dw.get(qq, {}).items():
                    if k.startswith('op_'):
                        ops[(o, k[3:])] += v
    print(f'== {agent}: {which.upper()} quadrant, {n} worlds; unlocked on day-start {st.mean(ud_list):.1f} (range {min(ud_list)}-{max(ud_list)})')
    print('\n1. tile states per day start (mean tiles of 25)')
    keys = ['crop', 'animal', 'empty structure', 'weed', 'empty: never used since unlock', 'empty: after harvest',
            'empty: after death / weed cleared', 'empty: animal / structure removed', 'empty: other']
    print('day  ' + ' '.join(f'{k[:14]:>14s}' for k in keys))
    for d in sorted(per_day):
        print(f'{d:3d}  ' + ' '.join(f'{per_day[d][k] / n:14.1f}' for k in keys))
    print('tile-days per game: ' + ', '.join(f'{k} {v / n:.1f}' for k, v in sorted(tdays.items(), key=lambda kv: -kv[1])))
    print('\n2. plantings on the quadrant by source and crop, per game')
    for s_, c in src.items():
        print(f'  {s_:36s} ' + ', '.join(f'{k.lower()} {v / n:.1f}' for k, v in c.most_common()) + f'  (total {sum(c.values()) / n:.1f})')
    print('\n3. dropped maintenance value at 23h by quadrant and op (module coins per game; kind = the module job kind)')
    for o in ('first', 'second', 'third', 'fourth'):
        items = [(k, v) for k, v in dropped.items() if k[0] == o]
        if not items:
            continue
        byc = Counter()
        for (oo, cmd, kind), v in items:
            byc[cmd] += v
        print(f'  {o:6s} total {sum(v for _, v in items) / n:7,.0f}: ' + ', '.join(f'{c} {v / n:,.0f}' for c, v in byc.most_common())
              + ' | executed ops ' + ', '.join(f'{c} {ops[(o, c)] / n:.0f}' for c in ('WATER', 'HARVEST', 'FERTILIZE', 'FEED', 'CARE', 'COLLECT_FERTILIZER', 'PLANT')))
        kinds = Counter()
        for (oo, cmd, kind), v in items:
            kinds[f'{cmd}/{kind}'] += v
        print('         by op/kind: ' + ', '.join(f'{k} {v / n:,.0f}' for k, v in kinds.most_common(8)))
    print('\n4. animals on the quadrant per day start (mean tiles)')
    days = sorted(anim_day)
    for sp in ('goose', 'cow', 'sheep'):
        print(f'  {sp:6s} ' + ' '.join(f'{anim_day[d][sp] / n:4.1f}' for d in days) + f'   (animal-days {sum(anim_day[d][sp] for d in days) / n:.0f})')
    print('         days ' + ' '.join(f'{d:4d}' for d in days))


def leaders(which, teams):
    per_day = defaultdict(Counter)
    src = defaultdict(Counter)
    anim_day = defaultdict(Counter)
    n = 0
    for f in sorted(glob.glob(str(ROOT / 'data/leader_semantics/*/*.json.gz'))):
        team = NAMES[Path(f).parent.name]
        if team not in teams:
            continue
        g = json.load(gzip.open(f, 'rt', encoding='utf-8'))
        B = [labs(d['board']) for d in g['days']]
        ud_ = unlock_days(B)
        od = ordinals(ud_)
        qs = [k for k, v in od.items() if v == which]
        if not qs:
            continue
        q = qs[0]
        n += 1
        ud = ud_[q]
        for d in range(ud, 30):
            c = Counter()
            for i in QTILES[q]:
                l = B[d][i]
                c['crop' if l in CROP_LAB else 'animal' if l in ANIM else 'empty or weed' if l == ' .' else 'other'] += 1
            per_day[d].update(c)
            for i in QTILES[q]:
                if B[d][i] in ANIM:
                    anim_day[d][ANIM[B[d][i]]] += 1
        for d, day in enumerate(g['days']):
            for crop, tl in day['planted'].items():
                for i in tl:
                    if quad(i) == q:
                        src['days <= 11' if d <= 11 else 'days >= 12'][crop] += 1
    print(f'\n== leaders {sorted(teams)}: {which.upper()} quadrant in {n} games')
    print('1. per day start (mean tiles of 25): day / crop / animal / empty-or-weed / other')
    for d in sorted(per_day):
        c = per_day[d]
        print(f'  {d:3d} {c["crop"] / n:5.1f} {c["animal"] / n:5.1f} {c["empty or weed"] / n:5.1f} {c["other"] / n:5.1f}')
    print('2. plantings by window: ' + ' | '.join(f'{s_}: ' + ', '.join(f'{k.lower()} {v / n:.1f}' for k, v in c.most_common()) for s_, c in src.items()))
    days = sorted(anim_day)
    print('4. animals per day start:')
    for sp in ('goose', 'cow', 'sheep'):
        print(f'  {sp:6s} ' + ' '.join(f'{anim_day[d][sp] / n:4.1f}' for d in days) + f'   (animal-days {sum(anim_day[d][sp] for d in days) / n:.0f})')


def main():
    a = sys.argv[1:]
    ddir = ROOT / (a[a.index('--dir') + 1] if '--dir' in a else 'results/fresh/lead_cycles')
    which = a[a.index('--quad') + 1] if '--quad' in a else 'third'
    if a[0] == 'leaders':
        teams = set(a[a.index('--teams') + 1].split(',')) if '--teams' in a else {'DSM', 'DECEM', 'Vadim', 'MG'}
        return leaders(which, teams)
    ours(a[0], ddir, which)


if __name__ == '__main__':
    main()
