"""Diff the two per-step traces from scripts/trace_y2_anomaly.py (mgt_lib584 vs mgt_y2 on ladder
world 111302438) and locate the mechanism behind y2 selling fewer wool units.

For each day: sheep-tile yield_units/bank/fed/cared at hour 23 (end of day, before the overnight
`_daily_refresh_animals` tick), who issued each HARVEST (tape crew vs the sheep-overlay's hidden
hands), shed WOOL and SELL WOOL orders, and the WOOL price at each sale. Flags the first day the
two runs' wool figures (units harvested, units sold, shed WOOL) diverge, and prints candidate
causes: a tile sitting at yield_units==max_held(6) when a production tick fires (the next batch is
swallowed), a HARVEST that finds yield_units==0 (no-op / already taken), or shed WOOL near the 100
cap right before a midnight drop.

Usage: .venv/Scripts/python.exe scripts/diff_y2_wool_trace.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'results/fresh/newphase_20260923/y2_anomaly'
MAX_HELD = 6


def load(name):
    return json.loads((DIR / f'trace_{name}.json').read_text(encoding='utf-8'))


def by_day(log):
    days = {}
    for row in log:
        days.setdefault(row['day'], []).append(row)
    return days


def tile_series(log, tile_key):
    """[(step, yield_units, bank, fed, cared) for this tile across all steps where it existed]."""
    out = []
    for row in log:
        for s in row['sheep']:
            if (s['x'], s['y']) == tile_key:
                out.append((row['step'], s['yield_units'], s['bank'], s['fed'], s['cared'], s['unfed']))
    return out


def all_tiles(log):
    keys = set()
    for row in log:
        for s in row['sheep']:
            keys.add((s['x'], s['y']))
    return sorted(keys)


def harvests(log, tile_key):
    """[(step, is_own, yield_units_before)] for HARVEST commands whose position matched this tile."""
    out = []
    for row in log:
        yb = next((s['yield_units'] for s in row['sheep'] if (s['x'], s['y']) == tile_key), None)
        for t in row['touches']:
            if t['cmd'] == 'HARVEST' and t['pos'] == list(tile_key):
                out.append((row['step'], t['is_own'], yb))
    return out


def main():
    base = load('mgt_lib584')
    y2 = load('mgt_y2')
    print(f"BASE final={base['summary']['final']} margin={base['summary']['margin']} "
          f"sold_wool={base['summary']['sold_wool']} revenue_wool={base['summary']['revenue_wool']}")
    print(f"Y2   final={y2['summary']['final']} margin={y2['summary']['margin']} "
          f"sold_wool={y2['summary']['sold_wool']} revenue_wool={y2['summary']['revenue_wool']}")
    print()

    blog, ylog = base['log'], y2['log']
    btiles, ytiles = all_tiles(blog), all_tiles(ylog)
    print(f'base sheep tiles ever seen: {btiles}')
    print(f'y2   sheep tiles ever seen: {ytiles}')
    print()

    # daily sold-wool and shed-wool trajectory (end-of-day, hour 23 snapshot -- BEFORE that step's
    # own action, i.e. reflects the day's accumulated state)
    def eod_rows(log):
        d = by_day(log)
        return {day: rows[-1] for day, rows in d.items() if rows}

    beod, yeod = eod_rows(blog), eod_rows(ylog)
    print(f"{'day':>3} {'base shed':>9} {'y2 shed':>8} {'base sellW':>10} {'y2 sellW':>9} {'base price':>10} {'y2 price':>9}")
    cum_sell_b = cum_sell_y = 0
    first_divergence = None
    for day in sorted(set(beod) | set(yeod)):
        rb, ry = beod.get(day), yeod.get(day)
        sb = sum(r['sell_wool'] for r in blog if r['day'] == day)
        sy = sum(r['sell_wool'] for r in ylog if r['day'] == day)
        cum_sell_b += sb
        cum_sell_y += sy
        pb = rb['wool_price'] if rb else None
        py = ry['wool_price'] if ry else None
        shb = rb['shed_wool'] if rb else None
        shy = ry['shed_wool'] if ry else None
        print(f"{day:>3} {str(shb):>9} {str(shy):>8} {sb:>10} {sy:>9} {str(pb):>10} {str(py):>9}")
        if first_divergence is None and cum_sell_b != cum_sell_y:
            first_divergence = day
    print(f'\nfirst day cumulative WOOL sell orders diverge: day {first_divergence}')
    print()

    # per-tile detail around and after the divergence day
    for name, log, tiles in (('BASE', blog, btiles), ('Y2', ylog, ytiles)):
        print(f'--- {name} sheep tiles ---')
        for tk in tiles:
            series = tile_series(log, tk)
            hv = harvests(log, tk)
            print(f'  tile {tk}: {len(series)} obs, placed_day~{next((s["placed_day"] for row in log for s in row["sheep"] if (s["x"],s["y"])==tk), None)}')
            # print end-of-day (hour 23) snapshot each day
            eod = {}
            for step, yu, bank, fed, cared, unfed in series:
                day, hour = step // 24, step % 24
                if hour == 23:
                    eod[day] = (yu, bank, fed, cared, unfed)
            for day in sorted(eod):
                yu, bank, fed, cared, unfed = eod[day]
                flag = ' <== AT CAP' if yu >= MAX_HELD else ''
                print(f'    day {day:>2} hour23: yield_units={yu} bank={bank} fed={fed} cared={cared} unfed={unfed}{flag}')
            for step, is_own, yb in hv:
                who = 'OVERLAY' if is_own else 'tape'
                flag = ' (no-op: yield_units was 0)' if yb == 0 else ''
                print(f'    HARVEST at step {step} (day {step//24} hour {step%24}) by {who}, yield_units_before={yb}{flag}')
        print()


if __name__ == '__main__':
    main()
