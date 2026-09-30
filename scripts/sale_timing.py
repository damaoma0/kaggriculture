"""Per-day (and per-hour for one day) sales of one product by both farms, arms compared on one world: replays the arms'
streams with the season_gap engine hooks and records every successful SELL of the product by side and step.
usage: sale_timing.py team:ep PRODUCT day0 day1 ARM[,ARM...] [--hours DAY]"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import season_gap as SG  # noqa: E402  (installs the engine hooks)
import upkeep_engine as UE  # noqa: E402

LOG = []
_inner = SG.E._commit_unit


def commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _inner(op, item, price, farm, private, market, shed_capacity)
    s = SG._side(farm)
    if r and s and op == 'SELL':
        LOG.append((SG.REC['w'].t, s, item, float(price)))
    return r


SG.E._commit_unit = commit


def main():
    game, prod, d0, d1, arms = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5].split(',')
    hday = int(sys.argv[sys.argv.index('--hours') + 1]) if '--hours' in sys.argv else None
    team, ep = game.split(':')
    tape = UE.load_tape(team, int(ep))
    res = {}
    for arm in arms:
        LOG.clear()
        stream = None if arm.lower() == 'leader' else json.loads(
            (ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text())['actions']
        C = SG.run(tape, stream)
        per = defaultdict(lambda: [0, 0.0])
        hr = defaultdict(lambda: [0, 0.0])
        allp = defaultdict(lambda: [0, 0.0])
        for t, s, item, p in LOG:
            if prod != 'ALL' and item != prod:
                continue
            allp[(t // 24, s, item)][0] += 1
            allp[(t // 24, s, item)][1] += p
            per[(t // 24, s)][0] += 1
            per[(t // 24, s)][1] += p
            if hday is not None and t // 24 == hday:
                hr[(t % 24, s)][0] += 1
                hr[(t % 24, s)][1] += p
        res[arm] = (per, hr, C['money|us'] - C['money|opp'], allp)
    if prod == 'ALL':
        items = sorted({k[2] for r in res.values() for k in r[3]})
        base = arms[0]
        for arm in arms[1:]:
            print(f'== {arm} - {base}: revenue difference by day and product (us / rival / margin)')
            for d in range(d0, d1 + 1):
                row = []
                tu = trv = 0.0
                for it in items:
                    du = res[arm][3][(d, 'us', it)][1] - res[base][3][(d, 'us', it)][1]
                    dr = res[arm][3][(d, 'opp', it)][1] - res[base][3][(d, 'opp', it)][1]
                    nu = res[arm][3][(d, 'us', it)][0] - res[base][3][(d, 'us', it)][0]
                    tu += du
                    trv += dr
                    if abs(du) > 1 or abs(dr) > 1:
                        row.append(f'{it[:5]} us {du:+.0f} ({nu:+d}u) riv {dr:+.0f}')
                print(f'   d{d}: us {tu:+.0f} rival {trv:+.0f} margin {tu - trv:+.0f} | ' + '; '.join(row))
        return
    for arm, (per, hr, mg, _) in res.items():
        print(f'== {arm} (season margin {mg:+.0f}): {prod} sold per day, us / rival (units @ avg price)')
        tu = tr = ru = rr = 0
        for d in range(d0, d1 + 1):
            u, ur = per[(d, 'us')], per[(d, 'opp')]
            tu += u[0]
            tr += u[1]
            ru += ur[0]
            rr += ur[1]
            print(f'   d{d}: us {u[0]:3d} @ {u[1] / u[0] if u[0] else 0:6.1f} = {u[1]:7.0f} | rival {ur[0]:3d} @ {ur[1] / ur[0] if ur[0] else 0:6.1f} = {ur[1]:7.0f}')
        print(f'   days {d0}-{d1}: us {tu} for {tr:.0f} | rival {ru} for {rr:.0f} | us - rival {tr - rr:+.0f}')
        if hday is not None:
            print(f'   day {hday} by hour: ' + ' '.join(f'h{h}:us{hr[(h, "us")][0]}@{hr[(h, "us")][1] / max(1, hr[(h, "us")][0]):.0f}/riv{hr[(h, "opp")][0]}@{hr[(h, "opp")][1] / max(1, hr[(h, "opp")][0]):.0f}'
                                             for h in range(24) if hr[(h, 'us')][0] or hr[(h, 'opp')][0]))


if __name__ == '__main__':
    main()
