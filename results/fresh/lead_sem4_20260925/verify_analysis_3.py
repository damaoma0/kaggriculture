"""Skeptic re-check (3/3): per-quadrant output at leader prices per held tile-day, the work ledger, removals and the
'out of proportion' claims of the sem4 gap analysis. Raw per-(arm, game) JSONs only; one process, no games.
"""
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import stats

OUT = Path(__file__).resolve().parent
ARMS = ['LEADER', 'T0', 'T', 'S', 'S0', 'D', 'Dp']
OURS = ARMS[1:]
PRODUCTS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']
CROPS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON']
QN = ['first', 'second', 'third', 'fourth']
QTILE = {'first': 'NW', 'second': 'NE', 'third': 'SW', 'fourth': 'SE'}
MAINT = ['WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE', 'COLLECT_FERTILIZER']
CUTOFF = {'STRAWBERRY': 13, 'TOMATO': 18, 'MELON': 19, 'WHEAT': 25, 'CARROT': 26}


def tci(x):
    x = np.asarray(x, float)
    m = x.mean()
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x))
    return m, m - h, m + h


W = json.loads((OUT / 'worlds.json').read_text(encoding='utf-8'))
worlds = {w['episode']: w for w in W['worlds']}
R = {a: {} for a in ARMS}
for a in ARMS:
    for f in sorted((OUT / a).glob('*.json')):
        r = json.loads(f.read_text(encoding='utf-8'))
        R[a][r['episode']] = r
E = sorted(worlds)
n = len(E)


def PL(e, p):
    t = R['LEADER'][e]['totals']
    return t['rev'].get(p, 0) / t['sold'][p] if t['sold'].get(p) else 0.0


def m(f, a):
    return float(np.mean([f(R[a][e], e) for e in E]))


# quadrant key sanity: 'first' is NW etc. in every file
qbad = sum(1 for a in ARMS for e in E for q in QN if R[a][e]['quadrants'].get(q, {}).get('quadrant', QTILE[q]) != QTILE[q])
print('quadrant label mismatches:', qbad)

# ---------------------------------------------------------------- per quadrant
print('\nper quadrant: held tile-days | occupied | output value at leader prices | per held td | per occupied td | '
      'gap to leader output (t CI)')
qval = {a: {e: {} for e in E} for a in ARMS}
for a in ARMS:
    for e in E:
        for q in QN:
            Q = R[a][e]['quadrants'].get(q)
            qval[a][e][q] = sum(v * PL(e, p) for p, v in Q['harvested'].items()) if Q else 0.0
for a in ('LEADER', 'T0', 'T', 'S', 'S0', 'D', 'Dp'):
    for q in QN:
        held = np.mean([R[a][e]['quadrants'][q]['unlocked_tile_days'] if q in R[a][e]['quadrants'] else 0 for e in E])
        occ = np.mean([sum(v for k, v in R[a][e]['quadrants'][q]['occ_tile_days'].items() if k != 'EMPTY')
                       if q in R[a][e]['quadrants'] else 0 for e in E])
        val = np.mean([qval[a][e][q] for e in E])
        gap = tci([qval['LEADER'][e][q] - qval[a][e][q] for e in E])
        # also mean of per-game ratios (alternative definition)
        pr = [qval[a][e][q] / R[a][e]['quadrants'][q]['unlocked_tile_days'] for e in E
              if q in R[a][e]['quadrants'] and R[a][e]['quadrants'][q]['unlocked_tile_days']]
        print(f'  {a:6s} {q:6s} {held:6.0f} {occ:6.0f} {val:9,.0f} {val / held if held else float("nan"):6.1f} '
              f'{val / occ if occ else float("nan"):6.1f}  gap {gap[0]:+8,.0f} ({gap[1]:+,.0f}..{gap[2]:+,.0f})'
              f'  [mean of per-game ratios {np.mean(pr) if pr else float("nan"):.1f}]')
for a in ('T', 'S', 'S0', 'D'):
    tot = np.mean([sum(qval['LEADER'][e].values()) - sum(qval[a][e].values()) for e in E])
    cg = np.mean([R['LEADER'][e]['final'] - R[a][e]['final'] for e in E])
    print(f'  {a}: output gap all quadrants {tot:,.0f}; cash gap {cg:,.0f}; shares: ' +
          ', '.join(f'{q} {np.mean([qval["LEADER"][e][q] - qval[a][e][q] for e in E]) / cg:.0%}' for q in QN) +
          f' (sum of shares {tot / cg:.0%})')

# third quadrant detail
print('\nthird quadrant, mean per game: weed tile-days, rot units, HARVEST ops, unwatered plants')
for a in ('LEADER', 'T', 'S'):
    q = lambda r: r['quadrants']['third']
    print(f'  {a:6s} weed {m(lambda r, e: q(r)["occ_tile_days"].get("WEED", 0), a):5.1f}  rot units '
          f'{m(lambda r, e: sum(q(r)["rot_units"].values()), a):5.1f}  HARVEST {m(lambda r, e: q(r)["ops"].get("HARVEST", 0), a):5.1f}'
          f'  unwatered {m(lambda r, e: sum(v for k, v in q(r)["deaths"].items() if k.startswith("unwatered")), a):4.1f}')

# T per product x quadrant: strawberry total
st_ = np.mean([sum((R['LEADER'][e]['quadrants'][q]['harvested'].get('STRAWBERRY', 0) -
                    R['T'][e]['quadrants'][q]['harvested'].get('STRAWBERRY', 0)) * PL(e, 'STRAWBERRY') for q in QN) for e in E])
wh_ = np.mean([sum((R['LEADER'][e]['quadrants'][q]['harvested'].get('WHEAT', 0) -
                    R['T'][e]['quadrants'][q]['harvested'].get('WHEAT', 0)) * PL(e, 'WHEAT') for q in QN) for e in E])
print(f'\nT gross output gap: strawberry {st_:,.0f}, wheat {wh_:,.0f}')

# ---------------------------------------------------------------- work ledger
print('\nwork ledger, mean per game')
for a in ARMS:
    t = lambda r: r['totals']
    maint = m(lambda r, e: sum(t(r)['eff_ops'].get(k, 0) for k in MAINT), a)
    moves = m(lambda r, e: t(r)['moves'], a)
    print(f'  {a:6s} unit-steps {m(lambda r, e: t(r)["unit_steps"], a):6.0f} moves {moves:6.0f} PASS {m(lambda r, e: t(r)["passes"], a):5.0f} '
          f'maint {maint:6.0f} (stored maint_ops_eff {m(lambda r, e: t(r)["maint_ops_eff"], a):6.0f}) moves/maint {moves / maint:.2f} '
          + ' '.join(f'{k[:5]} {m(lambda r, e, k=k: t(r)["eff_ops"].get(k, 0), a):5.0f}' for k in MAINT + ['PLANT', 'DIG'])
          + f' pickups {m(lambda r, e: t(r)["pickups"], a):4.0f} ({m(lambda r, e: t(r)["pickup_items"], a):4.0f}) '
          f'disc {m(lambda r, e: t(r)["discards_total"], a):5.1f} hires {m(lambda r, e: t(r)["hires"], a):4.0f} '
          f'wages {m(lambda r, e: t(r)["wages"], a):5.0f}')
for k in ('WATER', 'HARVEST', 'FERTILIZE'):
    print(f'  T vs LEADER {k}: {m(lambda r, e: r["totals"]["eff_ops"].get(k, 0), "T") / m(lambda r, e: r["totals"]["eff_ops"].get(k, 0), "LEADER") - 1:+.0%}')
print('  rot units W/C/S  LEADER', [round(m(lambda r, e, c=c: r['totals']['deaths'].get('rot_units_' + c, 0), 'LEADER'), 1) for c in ('WHEAT', 'CARROT', 'STRAWBERRY')],
      ' T', [round(m(lambda r, e, c=c: r['totals']['deaths'].get('rot_units_' + c, 0), 'T'), 1) for c in ('WHEAT', 'CARROT', 'STRAWBERRY')])

# ---------------------------------------------------------------- animals
print('\nanimals: bought / animal-days / escaped / product harvested, mean per game')
for a in ARMS:
    row = []
    for sp, prod in (('COW', 'MILK'), ('SHEEP', 'WOOL'), ('GOOSE', 'EGG')):
        bought = m(lambda r, e: r['totals']['bought'].get(sp, 0), a)
        days = m(lambda r, e: sum(Q['occ_tile_days'].get(sp, 0) for Q in r['quadrants'].values()), a)
        esc = m(lambda r, e: r['totals']['deaths'].get('escaped_' + sp, 0), a)
        h = m(lambda r, e: r['totals']['harvested'].get(prod, 0), a)
        row.append(f'{sp} {bought:4.1f}/{days:5.0f}/{esc:3.1f}/{h:5.0f}')
    empty = m(lambda r, e: sum(v for Q in r['quadrants'].values() for k, v in Q['occ_tile_days'].items()
                               if k in ('S_COOP', 'S_PASTURE')), a)
    empty2 = m(lambda r, e: sum(v for k, v in r['quadrants']['second']['occ_tile_days'].items() if k in ('S_COOP', 'S_PASTURE')), a)
    print(f'  {a:6s} ' + ' | '.join(row) + f' | empty coop/pasture td {empty:5.1f} (second q {empty2:4.1f})')

# ---------------------------------------------------------------- plantings inside the window
print('\nplantings per game: total (after cutoff) | in-window')
for a in ARMS:
    cells = []
    for c in CROPS:
        tot = m(lambda r, e: sum(dd.get('plant', {}).get(c, 0) for dd in r['days']), a)
        post = m(lambda r, e: sum(dd.get('plant', {}).get(c, 0) for d, dd in enumerate(r['days']) if d > CUTOFF[c]), a)
        cells.append(f'{c[:5]} {tot:5.1f} ({post:4.1f}) in {tot - post:5.1f}')
    print(f'  {a:6s} ' + ' | '.join(cells))

# ---------------------------------------------------------------- removals
print('\nremovals, mean per game')
for a in ARMS:
    t = lambda r: r['totals']
    lg = Counter()
    for e in E:
        lg.update({k: v for k, v in (R[a][e].get('agent_log') or {}).items() if k.startswith('rm_')})
    cells = []
    for c in ('STRAWBERRY', 'TOMATO'):
        cells.append(f'{c[:5]} plant {m(lambda r, e: t(r)["plant"].get(c, 0), a):4.1f} live {m(lambda r, e: t(r)["dug_live"].get(c, 0), a):4.1f} '
                     f'ended {m(lambda r, e: t(r)["deaths"].get("ended_" + c, 0), a):4.1f} rotted {m(lambda r, e: t(r)["deaths"].get("rotted_" + c, 0), a):4.1f} '
                     f'unw {m(lambda r, e: t(r)["deaths"].get("unwatered_" + c, 0), a):4.1f}')
    dug_ended = m(lambda r, e: sum(t(r)['dug_ended'].values()), a)
    dug_ended_days = m(lambda r, e: sum(sum(dd.get('dug_ended', {}).values()) for dd in r['days']), a)
    has_log = sum(1 for e in E if R[a][e].get('agent_log'))
    print(f'  {a:6s} ' + ' | '.join(cells) + f' | dug_ended {dug_ended:.1f}/{dug_ended_days:.1f} | issued S/T '
          f'{lg.get("rm_issued_STRAWBERRY", lg.get("rm_sel_STRAWBERRY", 0)) / n:.1f}/{lg.get("rm_issued_TOMATO", lg.get("rm_sel_TOMATO", 0)) / n:.1f} '
          f'forfeit {lg.get("rm_forfeit_prods", 0) / n:.1f} | games with an agent_log {has_log}/{n}')
