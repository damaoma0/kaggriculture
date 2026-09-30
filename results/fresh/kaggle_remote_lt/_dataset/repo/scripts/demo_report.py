"""Demo report for a few worlds: arms vs a base arm on the same worlds - margin / own / rival cash per world, strawberry
cluster trips (sd_tier_sclu summaries: trips a day, units a trip, extra-work tiles, drop hour), strawberries reaching the
shed by daytime return vs the midnight dump, and our unit-hours spent moving / idle (replayed from the streams).
usage: demo_report.py <worlds.txt> <BASE> <ARM>[,<ARM>...] [--workers 4]"""
import json
import statistics as stt
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
M = ROOT / 'results/fresh/sector_20260925/multi'
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}


def replay(args):
    g, arm = args
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    while w.t < 719:
        t = w.t
        own = s[t] if (t >= 264 and t < len(s) and isinstance(s[t], dict) and s[t]) else (UE.tape_action(tape['actions'], t) if t < 264 else dict(UE.PASS))
        if t >= 264:
            for a in [own.get('farmer')] + list(own.get('hands') or []):
                op = a[0] if isinstance(a, list) and a else 'PASS'
                c['move' if op in MOVES else ('idle' if op == 'PASS' else 'op')] += 1
        before = w.private(seat)['shed'].get('STRAWBERRY', 0)
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        sold = sum(int(o[2]) for o in (own.get('market') or []) if isinstance(o, list) and o and o[0] == 'SELL' and o[1] == 'STRAWBERRY')
        w.step(a2)
        if t >= 264:
            after = w.private(seat)['shed'].get('STRAWBERRY', 0)
            inflow = after - before + min(sold, before + max(0, after - before) + sold)   # approximate: sells come out of the shed
            inflow = max(0, after - before) if sold == 0 else max(0, after - before + sold)
            c['straw_day' if t % 24 != 23 else 'straw_night'] += inflow
    return g, arm, dict(c)


def main():
    wf, base, arms = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / wf).read_text().strip().replace('\n', ',').split(',')
    games = [g.strip() for g in games if g.strip()]
    res = {}
    for arm in [base] + arms:
        for g in games:
            d = json.loads((M / arm / f"{g.split(':')[1]}.json").read_text())
            m = d['money']['30']
            cl = []
            for v in (d.get('tier_days') or {}).values():
                cl += ((v or {}).get('sclu') or {}).get('clusters') or []
            res[(arm, g)] = {'own': m[0], 'riv': m[1], 'clusters': cl}
    with Pool(nw) as pool:
        for g, arm, c in pool.imap_unordered(replay, [(g, a) for a in [base] + arms for g in games]):
            res[(arm, g)].update(c)
    n = len(games)
    print(f'{n} worlds, per world; deltas vs {base}')
    for arm in arms:
        dm = [(res[(arm, g)]['own'] - res[(arm, g)]['riv']) - (res[(base, g)]['own'] - res[(base, g)]['riv']) for g in games]
        do = [res[(arm, g)]['own'] - res[(base, g)]['own'] for g in games]
        dr = [res[(arm, g)]['riv'] - res[(base, g)]['riv'] for g in games]
        cl = [c for g in games for c in res[(arm, g)]['clusters']]
        f = lambda k, a: stt.mean(res[(a, g)].get(k, 0) for g in games)
        print(f'\n{arm}: margin {stt.mean(dm):+.0f} (better {sum(1 for x in dm if x > 0)}/{n}; per world {", ".join(f"{x:+.0f}" for x in dm)})')
        print(f'   own {stt.mean(do):+.0f}, rival {stt.mean(dr):+.0f}')
        if cl:
            print(f'   cluster trips {len(cl) / n:.1f} a world ({len(cl) / n / 18:.2f} a day), units a trip {stt.mean(c["units"] for c in cl):.1f}, '
                  f'tiles a trip {stt.mean(len(c["tiles"]) for c in cl):.1f}, extra-work tiles a trip {stt.mean(len(c["extra"]) for c in cl):.1f}, '
                  f'drop hour mean {stt.mean(c["drop"] for c in cl):.1f} (median {stt.median(c["drop"] for c in cl)})')
            print(f'   strawberries delivered by the trips {sum(c["units"] for c in cl) / n:.0f} a world')
        print(f'   strawberries into the shed: daytime {f("straw_day", arm):.0f} vs {f("straw_day", base):.0f}, midnight {f("straw_night", arm):.0f} vs '
              f'{f("straw_night", base):.0f} | unit-hours moving {f("move", arm):.0f} vs {f("move", base):.0f}, idle {f("idle", arm):.0f} vs {f("idle", base):.0f}, '
              f'ops {f("op", arm):.0f} vs {f("op", base):.0f}')


if __name__ == '__main__':
    main()
