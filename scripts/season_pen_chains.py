"""How pen work is chained, leader game vs an arm's game (days 11-28, same world). Every unit-day becomes a sequence of
work visits (consecutive work steps of one unit on one tile): kind pen / crop / shed / other, ops done, hour.
Measures: pen-visit op combinations and order; per animal-day, visits and distinct units; pen CHAINS (maximal runs of
consecutive pen visits of one unit, walking allowed, no other work in between): length, spacing, hour, what precedes
and follows; concentration of pen work over hands.
usage: season_pen_chains.py <arm> <panel file | team:ep,...> <out.json> [--workers 2]"""
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
ACCESS = {tuple(p) for p in E._shed_access_tiles(10)}
AB = {'HARVEST': 'H', 'FEED': 'F', 'CARE': 'C', 'COLLECT_FERTILIZER': 'K', 'WATER': 'W', 'FERTILIZE': 'Z', 'PLANT': 'P',
      'DIG': 'D', 'DROP': 'd', 'PLACE': 'p', 'PICKUP': 'u', 'BUILD_COOP': 'B', 'BUILD_PASTURE': 'B'}
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST', 'PASS'}


def dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def close_day(C, seqs, pen_day):
    for i, sq in seqs.items():
        who = 'farmer' if i == 0 else 'hand'
        npen = 0
        for v in sq:
            if v['kind'] != 'pen':
                continue
            npen += 1
            ops = set(v['ops'])
            C['combo|' + ''.join(x for x in 'HFCK' if x in ops)] += 1
            C['pen_visits'] += 1
            C['pen_ops'] += len(v['ops'])
            C['order|' + v['ops']] += 1
            pd = pen_day[v['tile']]
            pd['visits'] += 1
            pd['units'].add(i)
            pd['ops'].update(v['ops'])
        C['pen_visits_per_unit|%d' % min(npen, 12)] += 1
        k = 0
        while k < len(sq):
            if sq[k]['kind'] != 'pen':
                k += 1
                continue
            j = k
            while j + 1 < len(sq) and sq[j + 1]['kind'] == 'pen':
                j += 1
            L = j - k + 1
            C['chain_len|%d' % min(L, 8)] += 1
            C['chains'] += 1
            C['chain_pens'] += L
            C['chain_start_h|%d' % (sq[k]['start'] // 4 * 4)] += 1
            for m in range(k, j):
                C['chain_gap_sum'] += dist(sq[m]['tile'], sq[m + 1]['tile'])
                C['chain_gaps'] += 1
            C['chain_ops'] += sum(len(sq[m]['ops']) for m in range(k, j + 1))
            C['chain_prev|' + (sq[k - 1]['kind'] if k > 0 else 'start')] += 1
            C['chain_next|' + (sq[j + 1]['kind'] if j + 1 < len(sq) else 'end')] += 1
            k = j + 1
        C['unitday|' + who] += 1
        if npen:
            C['unitday_pen|' + who] += 1
    for tile, pd in pen_day.items():
        C['pen_days'] += 1
        C['pen_day_visits|%d' % min(pd['visits'], 5)] += 1
        C['pen_day_units|%d' % min(len(pd['units']), 4)] += 1
        C['pen_day_full'] += int(all(pd['ops'].get(x, 0) for x in 'FCK'))
    shares = sorted((sum(1 for v in sq if v['kind'] == 'pen') for sq in seqs.values()), reverse=True)
    tot = sum(shares)
    if tot:
        C['conc_top2'] += sum(shares[:2]) / tot
        C['conc_top4'] += sum(shares[:4]) / tot
        C['conc_days'] += 1


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    C = Counter()
    seqs = defaultdict(list)
    pen_day = defaultdict(lambda: {'visits': 0, 'units': set(), 'ops': Counter()})
    while w.t < 696:
        t = w.t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        if t >= 264:
            f = w.farms[seat]
            pos = [tuple(f['farmer'])] + [tuple(p) for p in f['hands']]
            acts = [own.get('farmer')] + list(own.get('hands') or [])
            h = t % 24
            for i, p in enumerate(pos):
                a = acts[i] if i < len(acts) else None
                op = a[0] if isinstance(a, list) and a else 'PASS'
                if op in MOVES:
                    continue
                tl = f['tiles'][p[1]][p[0]]
                if isinstance(tl, dict) and 'animal' in tl:
                    kind = 'pen'
                elif p in ACCESS and op in ('DROP', 'PLACE', 'PICKUP'):
                    kind = 'shed'
                elif isinstance(tl, dict) and tl.get('kind') == 'PLANT':
                    kind = 'crop'
                else:
                    kind = 'other'
                sq = seqs[i]
                if sq and sq[-1]['tile'] == p and sq[-1]['end'] == h - 1:
                    sq[-1]['ops'] += AB.get(op, '?')
                    sq[-1]['end'] = h
                else:
                    sq.append({'tile': p, 'kind': kind, 'ops': AB.get(op, '?'), 'start': h, 'end': h})
            if h == 23:
                close_day(C, seqs, pen_day)
                seqs = defaultdict(list)
                pen_day = defaultdict(lambda: {'visits': 0, 'units': set(), 'ops': Counter()})
        acts2 = [None, None]
        acts2[seat], acts2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts2)
    return dict(C)


def job(args):
    g, arm = args
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    return ep, {'leader': run(tape, None), arm: run(tape, s['actions'])}


if __name__ == '__main__':
    arm, games, out = sys.argv[1], sys.argv[2], sys.argv[3]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    p = Path(games)
    games = p.read_text().replace(',', ' ').split() if p.exists() else games.split(',')
    res = {}
    with Pool(nw) as pool:
        for ep, r in pool.imap_unordered(job, [(g, arm) for g in games]):
            res[ep] = r
    json.dump(res, open(out, 'w'))
    print('done', len(res))
