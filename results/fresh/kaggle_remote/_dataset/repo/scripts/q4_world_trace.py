"""Serial driver for E1's scripts/lead_world_trace.py (read-only use of its run_one): per-day harvests, sales, failed
buys, bought units, shed contents and carried items at midnight and the shed-cap overflow, for our builds in
ladder-panel worlds. (lead_world_trace's own process pool is not used: an equivalent pool hung on Kaggle.)

usage: q4_world_trace.py run <agentA,agentB> <ep,ep,...> [submission=p2750]   -> results/fresh/lead_world_trace/<agent>_<ep>.json
       q4_world_trace.py wheat <agentA> <agentB> [--cycles results/fresh/lead_cycles]
The 'wheat' report is the per-game wheat (and every product's) balance, paired: harvested + bought - sold - fed -
overflow - held at the end (shed at the last midnight + carried) = residual (FEED commands from the lead_cycles labour
account; one FEED = one wheat).
"""
import json
import math
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/lead_world_trace'
T11 = 2.201


def ci(xs):
    m = st.mean(xs)
    if len(xs) < 2:
        return f'{m:+.1f}'
    s = st.stdev(xs) / math.sqrt(len(xs))
    return f'{m:+.1f} ({m - T11 * s:+.1f} .. {m + T11 * s:+.1f})'


def balance(tr, cyc):
    """per product: harvested, bought, sold, overflow, held at end; FEED commands (wheat) from the cycles record."""
    D = tr['days']
    h, b, s, ov = Counter(), Counter(), Counter(), Counter()
    for d in D:
        h.update(d['harv'])
        s.update(d['sold'])
        ov.update(d['overflow'])
        for k, v in d['bought'].items():
            op, item = k.split(':', 1)
            if op == 'BUY_PRODUCT':
                b[item] += v
    last = D[29]
    held = Counter(last.get('shed_mid') or {})
    held.update(last.get('carried_mid') or {})
    fed = 0
    fert_used = 0
    if cyc is not None:
        for dw in cyc.get('work', []):
            for q in ('NW', 'NE', 'SW', 'SE'):
                fed += dw.get(q, {}).get('op_FEED', 0)
                fert_used += dw.get(q, {}).get('op_FERTILIZE', 0)
    return dict(h=h, b=b, s=s, ov=ov, held=held, fed=fed, fert_used=fert_used,
                overflow_by_day=[sum(d['overflow'].values()) for d in D])


def wheat(A, B, cdir):
    eps = sorted({p.stem.split('_')[-1] for p in OUT.glob(f'{A}_*.json')} & {p.stem.split('_')[-1] for p in OUT.glob(f'{B}_*.json')})
    rows = {}
    for ag in (A, B):
        for e in eps:
            tr = json.load(open(OUT / f'{ag}_{e}.json'))
            cf = cdir / ag / f'{e}.json'
            cyc = json.load(open(cf)) if cf.exists() else None
            rows[(ag, e)] = balance(tr, cyc)
    n = len(eps)
    print(f'{A} vs {B}: {n} worlds; per game, with-SE / baseline / paired delta (t 95% CI)')
    for p in ('WHEAT', 'FERTILIZER', 'EGG', 'MILK', 'WOOL', 'STRAWBERRY', 'TOMATO', 'CARROT', 'MELON'):
        lines = []
        for key, lab in (('h', 'harvested/collected'), ('b', 'bought'), ('s', 'sold'), ('ov', 'overflow'), ('held', 'held at end')):
            xa = [rows[(A, e)][key].get(p, 0) for e in eps]
            xb = [rows[(B, e)][key].get(p, 0) for e in eps]
            if any(xa) or any(xb):
                lines.append(f'{lab} {st.mean(xa):.1f} / {st.mean(xb):.1f} / {ci([x - y for x, y in zip(xa, xb)])}')
        extra = ''
        if p == 'WHEAT':
            fa = [rows[(A, e)]['fed'] for e in eps]
            fb = [rows[(B, e)]['fed'] for e in eps]
            ra = [rows[(A, e)]['h'].get(p, 0) + rows[(A, e)]['b'].get(p, 0) - rows[(A, e)]['s'].get(p, 0) - rows[(A, e)]['fed']
                  - rows[(A, e)]['ov'].get(p, 0) - rows[(A, e)]['held'].get(p, 0) for e in eps]
            rb = [rows[(B, e)]['h'].get(p, 0) + rows[(B, e)]['b'].get(p, 0) - rows[(B, e)]['s'].get(p, 0) - rows[(B, e)]['fed']
                  - rows[(B, e)]['ov'].get(p, 0) - rows[(B, e)]['held'].get(p, 0) for e in eps]
            extra = f' | fed (FEED commands) {st.mean(fa):.1f} / {st.mean(fb):.1f} / {ci([x - y for x, y in zip(fa, fb)])} | residual {st.mean(ra):.1f} / {st.mean(rb):.1f}'
        if p == 'FERTILIZER':
            fa = [rows[(A, e)]['fert_used'] for e in eps]
            fb = [rows[(B, e)]['fert_used'] for e in eps]
            extra = f' | used (FERTILIZE commands) {st.mean(fa):.1f} / {st.mean(fb):.1f} / {ci([x - y for x, y in zip(fa, fb)])}'
        print(f'  {p}: ' + '; '.join(lines) + extra)
    oa = [sum(rows[(A, e)]['ov'].values()) for e in eps]
    ob = [sum(rows[(B, e)]['ov'].values()) for e in eps]
    print(f'  all items discarded by the shed cap: {st.mean(oa):.1f} / {st.mean(ob):.1f} / {ci([x - y for x, y in zip(oa, ob)])}')
    by = [st.mean(rows[(A, e)]['overflow_by_day'][d] for e in eps) for d in range(30)]
    bb = [st.mean(rows[(B, e)]['overflow_by_day'][d] for e in eps) for d in range(30)]
    print('  overflow by day with-SE : ' + ' '.join(f'{x:.1f}' for x in by))
    print('  overflow by day baseline: ' + ' '.join(f'{x:.1f}' for x in bb))


def main():
    if sys.argv[1] == 'wheat':
        a = sys.argv[1:]
        cdir = ROOT / (a[a.index('--cycles') + 1] if '--cycles' in a else 'results/fresh/lead_cycles')
        return wheat(sys.argv[2], sys.argv[3], cdir)
    import lead_world_trace as W
    agents, eps = sys.argv[2].split(','), sys.argv[3].split(',')
    sub = sys.argv[4] if len(sys.argv) > 4 else 'p2750'
    for e in eps:
        for a in agents:
            print(W.run_one(a, str(ROOT / f'data/ladder_panel/{sub}/{e}.json.gz')), flush=True)


if __name__ == '__main__':
    main()
