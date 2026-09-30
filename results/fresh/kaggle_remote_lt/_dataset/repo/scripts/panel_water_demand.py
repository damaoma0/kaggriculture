"""Keep-alive watering demand per day over the 40-world panel (days 11-28), the leader's game vs an arm's: at each day's
start, every plant that was dry yesterday (consecutive_unwatered >= 1: it dies unless watered today) is a must-water; the
rest may skip today. Per crop: must-water plants by day parity, the day-to-day spread (max / min / std over days 12-28),
and all waters done per day - how uneven the keep-alive load is.
usage: panel_water_demand.py <ARM> [--workers 4]"""
import json
import statistics as stt
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402


def play(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    must = defaultdict(Counter)                      # day -> crop -> plants that must be watered today
    plants = defaultdict(Counter)
    waters = Counter()
    while w.t < 696:
        t = w.t
        if t >= 264 and t % 24 == 0:
            for row in w.farms[seat]['tiles']:
                for tl in row:
                    if isinstance(tl, dict) and tl.get('kind') == 'PLANT':
                        plants[t // 24][tl['crop']] += 1
                        if tl.get('consecutive_unwatered', 0) >= 1:
                            must[t // 24][tl['crop']] += 1
        own = UE.tape_action(tape['actions'], t) if (stream is None or t < 264) else (stream[t] if isinstance(stream[t], dict) and stream[t] else dict(UE.PASS))
        if t >= 264:
            for a in [own.get('farmer')] + list(own.get('hands') or []):
                if isinstance(a, list) and a and a[0] == 'WATER':
                    waters[t // 24] += 1
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    return must, plants, waters


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    out = {}
    for lab, st_ in (('DSM', None), (arm, s)):
        m, p, wt = play(tape, st_)
        out[lab] = {'must': {d: dict(c) for d, c in m.items()}, 'plants': {d: dict(c) for d, c in p.items()}, 'waters': dict(wt)}
    return out


if __name__ == '__main__':
    arm = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    res = []
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm) for g in games]):
            res.append(r)
    for lab in ('DSM', arm):
        tot = Counter()
        spread = defaultdict(list)
        wsp = []
        for r in res:
            M = r[lab]['must']
            for d in range(12, 29):
                for crop in ('STRAWBERRY', 'WHEAT', 'TOMATO', 'CARROT'):
                    v = M.get(d, {}).get(crop, 0)
                    tot[(crop, d % 2)] += v
                    spread[crop].append((d, v))
                tot[('ALL', d % 2)] += sum(M.get(d, {}).values())
            ws = [r[lab]['waters'].get(d, 0) for d in range(12, 29)]
            ms = [sum(M.get(d, {}).values()) for d in range(12, 29)]
            wsp.append((stt.pstdev(ms), max(ms) - min(ms), stt.pstdev(ws)))
        n = len(res)
        print(f'{lab}: must-water plants per day (dry yesterday), mean over worlds, even / odd days:')
        for crop in ('ALL', 'STRAWBERRY', 'WHEAT', 'TOMATO', 'CARROT'):
            print(f'   {crop:10s} even {tot[(crop, 0)] / n / 9:.1f}  odd {tot[(crop, 1)] / n / 8:.1f}')
        print(f'   within a world: must-water std over days {stt.mean(x[0] for x in wsp):.1f}, max-min {stt.mean(x[1] for x in wsp):.1f}; all waters done std {stt.mean(x[2] for x in wsp):.1f}')
