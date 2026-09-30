"""Why the executor skipped planned ops (arm over the 40-world panel): for every tier_days breakage [step, unit, 'skip',
tile, op], the tile's state at that step in a replay: WATER - already watered today (by whom: an earlier op that day),
not a plant any more (harvested / dead / empty), or other; also whether the skipping unit's route ended early.
usage: panel_skip_reason.py <ARM> [--workers 4]"""
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    res = json.loads((ROOT / 'results/fresh/sector_20260925/multi' / arm / f'{ep}.json').read_text())
    br = defaultdict(list)
    for day, v in res['tier_days'].items():
        for b in (v or {}).get('breakages') or []:
            if len(b) >= 5 and b[2] == 'skip':
                br[int(b[0])].append((int(b[1]), int(b[3]), b[4]))
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    watered_by = {}                                       # (day, tile) -> (hour, unit) of the day's first WATER
    planted = {}
    while w.t < 696:
        t = w.t
        dd, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if t < 264 else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            for u, tile, op in br.get(t, ()):
                q = (tile % 10, tile // 10)
                tl = farm['tiles'][q[1]][q[0]]
                if op == 'WATER':
                    if not (isinstance(tl, dict) and tl.get('kind') == 'PLANT'):
                        k = 'not a plant now (' + ('empty' if tl is None else (tl.get('kind') if isinstance(tl, dict) else str(tl))) + ')'
                        if (dd, tile) in planted:
                            k += ', planted today'
                    elif tl.get('watered_today'):
                        wb = watered_by.get((dd, tile))
                        k = 'already watered today' + (' by the same unit' if wb and wb[1] == u else ' by another unit' if wb else ' (by whom unknown)')
                    else:
                        k = 'plant, not watered (?)'
                else:
                    k = 'state: ' + (json.dumps({kk: tl.get(kk) for kk in ('kind', 'crop', 'animal', 'yield_units', 'fed_today')}) if isinstance(tl, dict) else str(tl))[:60]
                c[op + ' | ' + k] += 1
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            for u, p in enumerate(units):
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                if op == 'WATER':
                    watered_by.setdefault((dd, p[1] * 10 + p[0]), (h, u))
                if op == 'PLANT':
                    planted[(dd, p[1] * 10 + p[0])] = h
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    return dict(c)


if __name__ == '__main__':
    arm = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = Counter()
    with Pool(nw) as pool:
        for c in pool.imap_unordered(job, [(g, arm) for g in games]):
            tot.update(c)
    n = len(games)
    print(f'{arm}: skipped planned ops a world, by the tile state at the skip')
    for k, v in tot.most_common(20):
        print(f'   {k:70s} {v / n:6.2f}')
