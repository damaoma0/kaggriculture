"""xfix: the day-11 single-day comparison from the leader's exact morning state (stored results only, no games).

For every arm in results/fresh/xfix_20260925/day11/<arm>/ (lead_ledger records of the single-day game, scripts/xfix_run.py
day11) against the leader (results/fresh/xopen_20260925/g1/LEADER, same worlds) and T (day11/T):
  - cash next morning (day 12, hour 0) vs the leader and vs T, paired over the 42 worlds (mean, t-CI, better/worse), the
    share of T's gap to the leader closed
  - day-11 ops: FERTILIZE / HARVEST / WATER by asset, PLANT, BUILD, animal PLACE (placements on the next-morning board),
    PASS, moves; revenue and sales by product; fertilizer collected / applied / sold / carried at midnight / discarded;
    next-morning tiles whose kind differs from the leader's
usage: xfix_day11_report.py [arm,arm,...]  -> results/fresh/xfix_20260925/day11_report.txt
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/xfix_20260925'
LEAD = ROOT / 'results/fresh/xopen_20260925/g1/LEADER'
D = 11
LINES = []


def say(s=''):
    LINES.append(s)
    print(s)


def tci(xs):
    from scipy import stats
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, m, m
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    return m, m - h, m + h


def load(arm):
    out = {}
    for f in (OUT / 'day11' / arm).glob('*.json'):
        r = json.loads(f.read_text(encoding='utf-8'))
        out[int(r['episode'])] = r
    return out


def animals_on(board):
    return Counter(k for k in (board or []) if k in ('GOOSE', 'COW', 'SHEEP'))


def main():
    arms = sys.argv[1].split(',') if len(sys.argv) > 1 else sorted(p.name for p in (OUT / 'day11').iterdir() if p.is_dir())
    W = json.loads((OUT / 'worlds42.json').read_text(encoding='utf-8'))['worlds']
    eps = [w['episode'] for w in W]
    L = {e: json.loads((LEAD / f'{e}.json').read_text(encoding='utf-8')) for e in eps}
    R = {a: load(a) for a in arms}
    T = R.get('T') or load('T')
    base_gap = [T[e]['days'][D + 1]['cash'] - L[e]['days'][D + 1]['cash'] for e in eps]
    say(f'day-11 single-day test from the leader\'s exact morning state, {len(eps)} worlds; T\'s cash gap next morning '
        f'{sum(base_gap) / len(base_gap):+,.0f}')
    say('| arm | n | cash next morning vs leader | vs T (paired, 95% CI) | better/worse vs T | gap closed |')
    say('|---|---:|---|---|---|---:|')
    for a in arms:
        es = [e for e in eps if e in R[a]]
        if not es:
            continue
        g = [R[a][e]['days'][D + 1]['cash'] - L[e]['days'][D + 1]['cash'] for e in es]
        v = [R[a][e]['days'][D + 1]['cash'] - T[e]['days'][D + 1]['cash'] for e in es]
        m, lo, hi = tci(v) if any(v) else (0.0, 0.0, 0.0)
        bg = sum(T[e]['days'][D + 1]['cash'] - L[e]['days'][D + 1]['cash'] for e in es) / len(es)
        say(f'| {a} | {len(es)} | {sum(g) / len(g):+,.0f} | {m:+,.0f} ({lo:+,.0f}..{hi:+,.0f}) | '
            f'{sum(1 for x in v if x > 0.5)}/{sum(1 for x in v if x < -0.5)} | {(1 - (sum(g) / len(g)) / bg) * 100 if bg else 0:.0f}% |')
    say('\nper-game means on day 11 (leader first, then each arm):')
    keys = [('FERTILIZE:WHEAT', 'opk'), ('FERTILIZE:STRAWBERRY', 'opk'), ('FERTILIZE:TOMATO', 'opk'), ('HARVEST:WHEAT', 'opk'),
            ('HARVEST:MELON', 'opk'), ('WATER:STRAWBERRY', 'opk'), ('WATER:WHEAT', 'opk'), ('PLANT', 'eff'), ('BUILD_COOP', 'eff'),
            ('BUILD_PASTURE', 'eff'), ('COLLECT_FERTILIZER', 'eff'), ('DROP', 'eff'), ('PLACE', 'eff')]
    sides = [('LEADER', L)] + [(a, R[a]) for a in arms]

    def mean(G, f):
        es = [e for e in eps if e in G]
        return sum(f(G[e]) for e in es) / max(1, len(es))
    for k, fld in keys:
        say(f'  {k:22s} ' + ' | '.join(f'{nm} {mean(G, lambda r: (r["days"][D].get(fld) or {}).get(k, 0)):.1f}' for nm, G in sides))
    say('  PASS                   ' + ' | '.join(f'{nm} {mean(G, lambda r: r["days"][D]["passes"]):.1f}' for nm, G in sides))
    say('  moves                  ' + ' | '.join(f'{nm} {mean(G, lambda r: r["days"][D]["move"]):.1f}' for nm, G in sides))
    for p in ('MELON', 'FERTILIZER', 'WHEAT', 'EGG', 'MILK'):
        say(f'  sold {p:17s} ' + ' | '.join(f'{nm} {mean(G, lambda r: (r["days"][D].get("sold") or {}).get(p, 0)):.1f}' for nm, G in sides))
    say('  revenue                ' + ' | '.join(f'{nm} {mean(G, lambda r: sum((r["days"][D].get("rev") or {}).values())):,.0f}' for nm, G in sides))
    say('  spend (trades)         ' + ' | '.join(f'{nm} {mean(G, lambda r: sum((r["days"][D].get("spend") or {}).values())):,.0f}' for nm, G in sides))
    say('  fertilizer carried mid ' + ' | '.join(f'{nm} {mean(G, lambda r: (r["days"][D].get("carried_mid") or {}).get("FERTILIZER", 0)):.1f}' for nm, G in sides))
    say('  melon carried mid      ' + ' | '.join(f'{nm} {mean(G, lambda r: (r["days"][D].get("carried_mid") or {}).get("MELON", 0)):.1f}' for nm, G in sides))
    say('  discarded at midnight  ' + ' | '.join(f'{nm} {mean(G, lambda r: sum((r["days"][D].get("overflow") or {}).values())):.1f}' for nm, G in sides))
    say('  animals next morning   ' + ' | '.join(f'{nm} {mean(G, lambda r: sum(animals_on(r["days"][D + 1].get("board_list")).values())):.1f}' for nm, G in sides))
    for a in arms:
        es = [e for e in eps if e in R[a]]
        dt = [sum(1 for x, y in zip(R[a][e]['days'][D + 1].get('board_list') or [], L[e]['days'][D + 1].get('board_list') or []) if x != y)
              for e in es]
        say(f'  {a}: next-morning tiles of another kind than the leader\'s: {sum(dt) / max(1, len(dt)):.1f}; agent log: ' +
            ', '.join(f'{k} {v / max(1, len(es)):.1f}' for k, v in sorted(sum((Counter({k2: v2 for k2, v2 in (R[a][e].get('agent_log') or {}).items()
                                                                                            if k2.startswith(('replant', 'fert_shadow', 'idle', 'lead_harvest'))})
                                                                                  for e in es), Counter()).items())))
    dl = [sum(1 for x, y in zip(T[e]['days'][D + 1].get('board_list') or [], L[e]['days'][D + 1].get('board_list') or []) if x != y) for e in eps]
    say(f'  (T: {sum(dl) / len(dl):.1f} tiles)')
    (OUT / 'day11_report.txt').write_text('\n'.join(LINES) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
