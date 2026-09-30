"""Strawberry sizing, diagnosis before building: in her 128 held-out recorded worlds (h2h arm A: mgt_m1 with her tape
for the world removed, her recorded tape opposing - frozen), compare OUR strawberry production with HERS, split by
the mismatch between the world's strawberry-buying shops and those of the final tape we followed, early (shops 1-4)
and late (5-8). Units and revenue sold come from the per-day ledgers; planting days from the router's tape boards
are not needed: the daily units sold by day show when the gap opens.
"""
import gzip, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LOO = ROOT / 'results/fresh/mg_tape/loo'
BUYS_STRAW = {'BRUNCH_SPOT', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP', 'FARMERS_MARKET'}


def seq(sh):
    out, seen = [], 0
    for cur in sh:
        while len(cur) > seen:
            out.append(cur[seen]); seen += 1
    return out[:8]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    tapes = {}
    for p in (ROOT / 'data/mg_tapes').rglob('*.json.gz'):
        g = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        tapes[g['episode']] = dict(shops=seq(g['shops']), boards=g['boards'])
    rows = []
    for f in LOO.glob('mgtape_vs_mgt_m1-mg_vs-*.json'):
        r = json.loads(f.read_text(encoding='utf-8'))
        hist = r.get('rival_history') or []
        if not hist or hist[-1][1] not in tapes:
            continue
        world = list(r['shops'])
        tape = tapes[hist[-1][1]]
        her = tapes.get(r['episode'])
        ws = lambda s: sum(x in BUYS_STRAW for x in s)
        # strawberry tiles on day-start boards: our final tape's recording (a proxy for our farm after the switch)
        # and her own recording in this world (exact for her)
        st = lambda b: (lambda s: sum(s[i:i + 2] == 'ST' for i in range(0, len(s), 2)))(''.join(b) if isinstance(b, list) else b)
        units = lambda daily, a, b: sum(d.get('STRAWBERRY', 0) for d in daily[a:b])
        rows.append(dict(ep=r['episode'], margin=-r['margin'],
                         mis_late=ws(world[4:]) - ws(tape['shops'][4:]), mis_early=ws(world[:4]) - ws(tape['shops'][:4]),
                         tiles_tape={d: st(tape['boards'][d]) for d in (12, 15, 18, 21)},
                         tiles_her={d: st(her['boards'][d]) for d in (12, 15, 18, 21)} if her else None,
                         u_ours=r['rival_sold'].get('STRAWBERRY', 0), u_hers=r['sold'].get('STRAWBERRY', 0),
                         rev_ours=r['rival_revenue'].get('STRAWBERRY', 0), rev_hers=r['revenue'].get('STRAWBERRY', 0),
                         late_ours=units(r['rival_units_daily'], 20, 30) - units(r['rival_units_daily'], 20, 21) if r.get('rival_units_daily') else 0))
    print(f'{len(rows)} worlds; ours = mgt_m1 ladder case, hers = her recorded tape (frozen); strawberry tiles are day-start board counts')
    print(f"{'late strawberry shops: world - tape':36s} {'n':>3s} {'margin':>8s} | {'tiles d12 tape/her':>18s} | {'d15':>9s} | {'d18':>9s} | {'units us/her':>12s} | {'revenue us/her':>15s}")
    for lab, sel in (('world has MORE (+1..)', lambda r: r['mis_late'] > 0), ('equal', lambda r: r['mis_late'] == 0),
                     ('world has FEWER', lambda r: r['mis_late'] < 0)):
        rs = [r for r in rows if sel(r) and r['tiles_her']]
        if not rs:
            continue
        t = lambda k, d: np.mean([r[k][d] for r in rs])
        m = lambda k: np.mean([r[k] for r in rs])
        print(f"{lab:36s} {len(rs):>3d} {m('margin'):>+8,.0f} | {t('tiles_tape', 12):>7.1f} / {t('tiles_her', 12):<8.1f} | {t('tiles_tape', 15):>4.1f}/{t('tiles_her', 15):<4.1f} | "
              f"{t('tiles_tape', 18):>4.1f}/{t('tiles_her', 18):<4.1f} | {m('u_ours'):>5.0f} / {m('u_hers'):<5.0f} | {m('rev_ours'):>6,.0f} / {m('rev_hers'):<6,.0f}")
    (ROOT / 'results/fresh/newphase_20260923/late_strawberry_gap.json').write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    main()
