"""Late-Yarn response, diagnosis before building: in her 128 held-out recorded worlds (h2h arm A = mgt_m1 with her
tape for the world removed; her recorded tape in the other seat), compare OUR sheep with HERS after a Yarn Store
reveal, split by whether the world got more late (shops 5-8) Yarn Stores than the tape we ended on.

Source: results/fresh/mg_tape/loo/mgtape_vs_mgt_m1-mg_vs-<ep>.json (trace.service = hour-23 snapshot per day and side:
species -> [count, fed, cared, pending bank, yield]; side 0 = HER seat, 1 = ours - mgt_loo logs its own seat first),
router history (our final tape) and daily units sold. Frozen opponent: her recorded moves.
"""
import gzip, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LOO = ROOT / 'results/fresh/mg_tape/loo'


def seq(sh):
    out, seen = [], 0
    for cur in sh:
        while len(cur) > seen:
            out.append(cur[seen]); seen += 1
    return out[:8]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    tape_shops = {}
    for p in (ROOT / 'data/mg_tapes').rglob('*.json.gz'):
        g = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        tape_shops[g['episode']] = seq(g['shops'])
    rows = []
    for f in LOO.glob('mgtape_vs_mgt_m1-mg_vs-*.json'):
        r = json.loads(f.read_text(encoding='utf-8'))
        world = list(r['shops'])
        hist = r.get('rival_history') or []
        if not hist:
            continue
        final = hist[-1][1]
        ts = tape_shops.get(final)
        if not ts:
            continue
        wl, tl = sum(s == 'YARN_STORE' for s in world[4:]), sum(s == 'YARN_STORE' for s in ts[4:])
        svc = r['trace']['service']
        her, ours = svc[0], svc[1]

        def sheep(side, days):
            c = fed = cared = 0
            for d in days:
                if d < len(side):
                    v = side[d].get('SHEEP')
                    if v:
                        c += v[0]; fed += v[1]; cared += v[2]
            n = max(1, len(days))
            return c / n, fed / max(1, c), cared / max(1, c)
        first_late = next((3 * (i + 1) for i, s in enumerate(world) if s == 'YARN_STORE' and i >= 4), None)
        late_days = list(range(first_late, 30)) if first_late else list(range(15, 30))
        wool_us = sum(u.get('WOOL', 0) for u in r['rival_units_daily'][-1:]) if r.get('rival_units_daily') else None
        rows.append(dict(ep=r['episode'], margin=-r['margin'], world_late=wl, tape_late=tl, mis=wl - tl, first_late=first_late,
                         ours=sheep(ours, late_days), hers=sheep(her, late_days),
                         ours12=sheep(ours, [12]), hers12=sheep(her, [12]),
                         wool_ours=(r.get('rival_sold') or {}).get('WOOL'), wool_hers=(r.get('sold') or {}).get('WOOL'),
                         wool_rev_ours=(r.get('rival_revenue') or {}).get('WOOL'), wool_rev_hers=(r.get('revenue') or {}).get('WOOL')))
    print(f'{len(rows)} worlds (ours = mgt_m1 ladder case, hers = her recorded tape; margins ours - hers)')
    print(f"{'late Yarn: world - tape':26s} {'n':>3s} {'margin':>8s} | {'sheep d12 us/her':>16s} | {'sheep after reveal us/her':>25s} | {'fed% us/her':>11s} | {'cared% us/her':>13s} | {'wool units us/her':>17s} | {'wool rev us/her':>15s}")
    for lab, sel in (('world has MORE (+1,+2)', lambda r: r['mis'] > 0), ('equal, world has late Yarn', lambda r: r['mis'] == 0 and r['world_late'] > 0),
                     ('equal, no late Yarn', lambda r: r['mis'] == 0 and r['world_late'] == 0), ('world has FEWER', lambda r: r['mis'] < 0)):
        rs = [r for r in rows if sel(r)]
        if not rs:
            continue
        m = lambda k, i: np.mean([r[k][i] for r in rs])
        w = lambda k: np.mean([r[k] or 0 for r in rs])
        print(f"{lab:26s} {len(rs):>3d} {np.mean([r['margin'] for r in rs]):>+8,.0f} | {m('ours12', 0):>6.1f} / {m('hers12', 0):<7.1f} | "
              f"{m('ours', 0):>10.1f} / {m('hers', 0):<12.1f} | {100 * m('ours', 1):>3.0f} / {100 * m('hers', 1):<5.0f} | {100 * m('ours', 2):>4.0f} / {100 * m('hers', 2):<6.0f} | "
              f"{w('wool_ours'):>7.0f} / {w('wool_hers'):<7.0f} | {w('wool_rev_ours'):>6,.0f} / {w('wool_rev_hers'):<6,.0f}")
    (ROOT / 'results/fresh/newphase_20260923/late_yarn_service_gap.json').write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    main()
