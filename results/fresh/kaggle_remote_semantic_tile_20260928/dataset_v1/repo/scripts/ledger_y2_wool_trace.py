"""Precise per-tile wool ledger from the two traces written by scripts/trace_y2_anomaly.py:
for every sheep tile, every HARVEST event's collected units (yield_units just before the command,
which the engine zeroes and hands to the harvester -- kaggriculture.py `_apply_unit_action`
HARVEST branch, line ~464), split into tape-crew vs sheep-overlay hidden-hand harvests, tape
no-ops (yield_units already 0 -- the overlay got there first), and the running total collected per
tile, so the total gap between the two runs' WOOL harvested can be attributed tile by tile.

Usage: .venv/Scripts/python.exe scripts/ledger_y2_wool_trace.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'results/fresh/newphase_20260923/y2_anomaly'


def load(name):
    return json.loads((DIR / f'trace_{name}.json').read_text(encoding='utf-8'))


def all_tiles(log):
    keys = set()
    for row in log:
        for s in row['sheep']:
            keys.add((s['x'], s['y']))
    return sorted(keys)


def tile_harvest_ledger(log, tile_key):
    """[(step, is_own, units_collected_or_0_if_noop)]"""
    out = []
    for row in log:
        yb = next((s['yield_units'] for s in row['sheep'] if (s['x'], s['y']) == tile_key), None)
        for t in row['touches']:
            if t['cmd'] == 'HARVEST' and t['pos'] == list(tile_key):
                out.append((row['step'], t['is_own'], yb or 0))
    return out


def main():
    base = load('mgt_lib584')
    y2 = load('mgt_y2')
    blog, ylog = base['log'], y2['log']
    tiles = sorted(set(all_tiles(blog)) | set(all_tiles(ylog)))
    print(f"{'tile':>8} {'base_units':>10} {'base_tape':>9} {'base_own':>8} {'base_noop':>9}  "
          f"{'y2_units':>8} {'y2_tape':>7} {'y2_own':>6} {'y2_noop':>7}  {'delta':>6}")
    tot_b = tot_y = 0
    tot_noop_b = tot_noop_y = 0
    tot_own_units_y = tot_own_units_b = 0
    for tk in tiles:
        lb = tile_harvest_ledger(blog, tk)
        ly = tile_harvest_ledger(ylog, tk)
        ub = sum(u for _, _, u in lb)
        uy = sum(u for _, _, u in ly)
        tape_b = sum(u for _, own, u in lb if not own)
        own_b = sum(u for _, own, u in lb if own)
        tape_y = sum(u for _, own, u in ly if not own)
        own_y = sum(u for _, own, u in ly if own)
        noop_b = sum(1 for _, _, u in lb if u == 0)
        noop_y = sum(1 for _, _, u in ly if u == 0)
        tot_b += ub
        tot_y += uy
        tot_noop_b += noop_b
        tot_noop_y += noop_y
        tot_own_units_b += own_b
        tot_own_units_y += own_y
        flag = '  <-- LOSS' if uy < ub else ('  <-- GAIN' if uy > ub else '')
        print(f"{str(tk):>8} {ub:>10} {tape_b:>9} {own_b:>8} {noop_b:>9}  "
              f"{uy:>8} {tape_y:>7} {own_y:>6} {noop_y:>7}  {uy - ub:>+6}{flag}")
    print(f"\n{'TOTAL':>8} {tot_b:>10} {'':>9} {tot_own_units_b:>8} {tot_noop_b:>9}  "
          f"{tot_y:>8} {'':>7} {tot_own_units_y:>6} {tot_noop_y:>7}  {tot_y - tot_b:>+6}")
    print(f"\nsummary sold_wool: base={base['summary']['sold_wool']} y2={y2['summary']['sold_wool']} "
          f"(delta {y2['summary']['sold_wool'] - base['summary']['sold_wool']:+d})")
    print(f"tile-level harvested-units delta: {tot_y - tot_b:+d} "
          f"(vs sold-units delta {y2['summary']['sold_wool'] - base['summary']['sold_wool']:+d} "
          f"-- difference is timing/shed-cap/order-queue effects on top of the harvest-unit gap)")


if __name__ == '__main__':
    main()
