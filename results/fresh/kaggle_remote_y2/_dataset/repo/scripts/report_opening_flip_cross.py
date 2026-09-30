"""Table for the opening x flip cross-test (scripts/opening_flip_cross.py), plus the spoiling threshold."""
import glob, json, random, statistics as st
from market_corpus import ROOT

OUT = ROOT / 'results/fresh/opening_flip_cross'
TAPE = ROOT / 'results/fresh/tape_vs_bench'


def ci(v, n=10000, seed=5):
    rng = random.Random(seed)
    d = sorted(st.mean(rng.choice(v) for _ in v) for _ in range(n))
    return d[int(0.025 * n)], d[int(0.975 * n) - 1]


def main():
    cells = {}
    for p in glob.glob(str(OUT / '*.json')):
        r = json.loads(open(p, encoding='utf-8').read())
        cells.setdefault((r['row'], r['flip']), []).append(r)
    print('## Opening x flip, our side in Mother-Goose\'s seat of her 30 worlds, against the live frozen benchmark (flip 70)')
    print(f"{'opening':18s} {'flip':7s} {'n':>3s} {'cash end d0':>11s} {'cash end d1':>11s} {'cash d12':>9s} "
          f"{'hire fail d1':>12s} {'plan intact':>11s} {'W-T-L':>9s} {'margin (95% CI)':>28s}")
    summary = {}
    for row, label in (('ours', 'current (V45)'), ('mg', 'MG-style (her plan)')):
        for flip in ('own', 'flip70', 'flip5', 'flip0', 'nash5'):
            rs = cells.get((row, flip))
            if not rs:
                continue
            m = [r['margin'] for r in rs]
            lo, hi = ci(m)
            hf = sum(r['hire_fail_d1'] for r in rs)
            intact = (f"{sum(1 for r in rs if r['board_exact_until'] is None or r['board_exact_until'] >= 240)}/{len(rs)}"
                      if row == 'mg' else 'n/a')
            w = sum(x > 0 for x in m); t = sum(x == 0 for x in m); l = sum(x < 0 for x in m)
            name = {'own': 'her 13/5/13'}.get(flip, flip)
            print(f"{label:18s} {name:7s} {len(rs):3d} {st.mean(r['cash_d0'] for r in rs):11.0f} "
                  f"{st.mean(r['cash_d1'] for r in rs):11.0f} {st.mean(r['cash_d12'] for r in rs):9.0f} "
                  f"{f'{hf}/{len(rs)}':>12s} {intact:>11s} {f'{w}-{t}-{l}':>9s} "
                  f"{st.mean(m):+9,.0f} ({lo:+8,.0f} to {hi:+8,.0f})")
            summary[f'{row}/{flip}'] = dict(n=len(rs), cash_d0=st.mean(r['cash_d0'] for r in rs),
                                            cash_d1=st.mean(r['cash_d1'] for r in rs),
                                            cash_d12=st.mean(r['cash_d12'] for r in rs), hire_fail=hf,
                                            margin=st.mean(m), ci=(lo, hi), w=w, t=t, l=l)
        print()
    print('## Spoiling threshold: her recorded plan (own 13/5/13 opening) against our benchmark with a turn-0 flip of q')
    extra = {0: 0, 5: 9, 6: 10, 7: 15, 8: 16, 10: 18, 35: 28, 70: 38}
    rows = [(0, 'sp_flip0'), (5, 'sp_flip5'), (6, 'sp_flip6'), (7, 'sp_flip7'), (8, 'sp_flip8'), (10, 'sp_flip10'), (35, 'sp_flip35')]
    for q, name in rows:
        rs = [json.loads(open(p, encoding='utf-8').read()) for p in glob.glob(str(TAPE / 'flip' / f'{name}-c0-*.json'))]
        if not rs:
            continue
        broke = sum(1 for r in rs if r['tape_daily'][2]['physical'].get('missing_worker_commands', 0) > 0)
        m = [r['margin'] for r in rs]
        print(f"   our flip {q:3d} (her extra opening cost +{extra[q]:2d}): her day-1 hire fails in {broke:2d}/{len(rs)} games; "
              f"her margin {st.mean(m):+9,.0f}")
    rs = [json.loads(open(p, encoding='utf-8').read()) for p in glob.glob(str(TAPE / 'mg-*.json'))]
    if rs:
        broke = sum(1 for r in rs if r['tape_daily'][2]['physical'].get('missing_worker_commands', 0) > 0)
        print(f"   our flip  70 (her extra opening cost +38): her day-1 hire fails in {broke:2d}/{len(rs)} games; "
              f"her margin {st.mean(r['margin'] for r in rs):+9,.0f}")
    (ROOT / 'results/fresh/opening_flip_cross_summary.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
