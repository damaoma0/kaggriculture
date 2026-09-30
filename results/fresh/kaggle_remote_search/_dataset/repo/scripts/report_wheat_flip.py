"""Opening wheat flip: is 70 bad for us, or a spoiler that hurts the opponent more?

Two measurements, both against fixed references:
  1. Self-play gate (seeds 173000-173015): flip 0 / 5 / 35 / 70 and the certified Nash opening (buy 5,
     keep) against the frozen benchmark, which flips 70. flip 70 must reproduce the null exactly.
     Reported as W-T-L and margin, plus own-cash and benchmark-cash deltas against the null on the
     same seeds, so a margin change can be attributed to our side or theirs.
  2. Mother-Goose's recorded tape against each variant playing live, without a cash cushion. Her
     opening is budget-exact, so the question is how much of her tape each flip size breaks, and what
     that does to the margin. The frozen benchmark (flip 70) arm is the existing tape_vs_bench 'mg' arm.
"""
import glob, json, statistics as st
from market_corpus import ROOT
import report_tape_vs_bench as T

SP = ROOT / 'results/fresh/selfplay'
TAPE = ROOT / 'results/fresh/tape_vs_bench'
ARMS = ['sp_flip0', 'sp_flip5', 'sp_flip35', 'sp_flip70', 'sp_nash5']


def gate():
    rows = {}
    for path in glob.glob(str(SP / 'games' / '*-173*.json')):
        r = json.loads(open(path, encoding='utf-8').read())
        rows.setdefault(r['candidate'], []).append(r)
    null = {(r['seed'], r['seat']): r for r in rows.get('sp_null', [])}
    print('## 1. Self-play gate against the frozen benchmark (seeds 173000-173015, both seats)')
    print(f"{'arm':12s} {'W-T-L':>9s} {'margin (95% CI)':>28s} {'own cash vs null':>17s} {'bench cash vs null':>19s}")
    out = {}
    for arm in ARMS:
        rs = rows.get(arm, [])
        if not rs:
            continue
        w = sum(r['margin'] > 0 for r in rs)
        t = sum(r['margin'] == 0 for r in rs)
        l = sum(r['margin'] < 0 for r in rs)
        m = [r['margin'] for r in rs]
        lo, hi = T.ci(m)
        own = [r['cash'] - null[(r['seed'], r['seat'])]['cash'] for r in rs if (r['seed'], r['seat']) in null]
        opp = [r['bench_cash'] - null[(r['seed'], r['seat'])]['bench_cash'] for r in rs if (r['seed'], r['seat']) in null]
        ol, oh = T.ci(own)
        bl, bh = T.ci(opp)
        out[arm] = dict(wins=w, ties=t, losses=l, margin=st.mean(m), ci=(lo, hi), own=st.mean(own), own_ci=(ol, oh),
                        bench=st.mean(opp), bench_ci=(bl, bh), n=len(rs))
        print(f"{arm:12s} {f'{w}-{t}-{l}':>9s} {st.mean(m):+9,.0f} ({lo:+7,.0f} to {hi:+7,.0f}) "
              f"{st.mean(own):+8,.0f} ({ol:+,.0f}..{oh:+,.0f}) {st.mean(opp):+8,.0f} ({bl:+,.0f}..{bh:+,.0f})")
    return out


def tape():
    print('\n## 2. Mother-Goose\'s recorded tape against each opening variant, live, no cash cushion')
    arms = {'sp_flip70 (frozen benchmark)': list(T.load().get('mg', {}).values())}
    for arm in ('sp_flip0', 'sp_flip5', 'sp_flip35', 'sp_nash5'):
        arms[arm] = [json.loads(open(p, encoding='utf-8').read())
                     for p in glob.glob(str(TAPE / 'flip' / f'{arm}-c0-*.json'))]
    arms['sp_nash5, cushion 40'] = [json.loads(open(p, encoding='utf-8').read())
                                    for p in glob.glob(str(TAPE / 'flip' / 'sp_nash5-c40-*.json'))]
    print(f"{'our opening':30s} {'n':>3s} {'MG W-T-L':>9s} {'MG margin (95% CI)':>27s} {'MG day-0 wheat cost':>20s} "
          f"{'hire fails day 1':>16s} {'board exact all game':>21s} {'coherent all game':>18s}")
    out = {}
    for arm, rs in arms.items():
        if not rs:
            continue
        m = [r['margin'] for r in rs]
        lo, hi = T.ci(m)
        cost = st.mean(r['tape_daily'][1]['spend'].get('BUY_PRODUCT:WHEAT', 0) - r['tape_daily'][1]['revenue'].get('WHEAT', 0)
                       for r in rs)
        hire_fail = sum(1 for r in rs if r['tape_daily'][2]['physical'].get('missing_worker_commands', 0) > 0)
        exact = sum(1 for r in rs if r['validity']['t_exact'] is None)
        coherent = sum(1 for r in rs if T.breaks(r)[1] is None)
        w = sum(x > 0 for x in m)
        t = sum(x == 0 for x in m)
        l = sum(x < 0 for x in m)
        out[arm] = dict(n=len(rs), mg_margin=st.mean(m), ci=(lo, hi), day0_net_wheat_cost=cost,
                        hire_fail_games=hire_fail, exact_games=exact, coherent_games=coherent)
        print(f"{arm:30s} {len(rs):3d} {f'{w}-{t}-{l}':>9s} {st.mean(m):+9,.0f} ({lo:+7,.0f} to {hi:+7,.0f}) "
              f"{cost:20.0f} {f'{hire_fail}/{len(rs)}':>16s} {f'{exact}/{len(rs)}':>21s} {f'{coherent}/{len(rs)}':>18s}")
    return out


def main():
    summary = dict(gate=gate(), tape=tape())
    (ROOT / 'results/fresh/wheat_flip_summary.json').write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')


if __name__ == '__main__':
    main()
