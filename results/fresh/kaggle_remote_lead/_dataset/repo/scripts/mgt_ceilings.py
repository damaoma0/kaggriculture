"""Hindsight ceilings for closing the gap to her original tape (ladder case, her recorded worlds).

Reads the head-to-head results of mgt_loo.py (her tape in her seat, our build live). Every ceiling is reported as the
paired gain over the baseline `mg_vs` (her tape for the world removed from our library) on the same worlds, next to
the gap itself (baseline minus `mg_vs_only`, where we play her tape for that world).

arms:  mg_oracle   her tape removed; the router ranks against the world's FULL shop list from day 3 (perfect
                   foresight of the shops, same library, same compatibility limit)
       mg_sell<D>  a neighbour's crew and purchases, HER sell orders from day D (perfect sell schedule for the world)
       mg_late<D>  her tape hidden until day D, then forced (a perfect plan adopted at day D, transition cost included)
usage: mgt_ceilings.py [hook_agent=mgt_m1o] [base_agent=mgt_m1]
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOO = ROOT / 'results/fresh/mg_tape/loo'


def ci(xs, n=10000, seed=7):
    rng = random.Random(seed)
    k = len(xs)
    m = sorted(sum(rng.choices(xs, k=k)) / k for _ in range(n))
    return m[int(0.025 * n)], m[int(0.975 * n)]


def main():
    hook = sys.argv[1] if len(sys.argv) > 1 else 'mgt_m1o'
    base = sys.argv[2] if len(sys.argv) > 2 else 'mgt_m1'
    files = sorted(p for s in ('56266758', '56266899') for p in (ROOT / 'data/mg_tapes' / s).glob('*.json.gz'))
    random.Random(20260920).shuffle(files)
    eps = [p.name.split('.')[0] for p in files[80:208]]

    def load(agent, arm):
        out = {}
        for ep in eps:
            f = LOO / f'mgtape_vs_{agent}-{arm}-{ep}.json'
            if f.exists():
                out[ep] = json.loads(f.read_text(encoding='utf-8'))
        return out

    A, B = load(base, 'mg_vs'), load(base, 'mg_vs_only')
    print(f'{"arm":<12} {"n":>4} {"W-L vs her tape":>16} {"mean margin":>12} | {"gain over the ladder case (95% CI)":>38} {"better/worse":>13} | {"share of the gap closed":>23} | {"dead cmds":>9} {"switches>12":>11}')
    for arm in ('mg_vs', 'mg_oracle', 'mg_sell12', 'mg_late12', 'mg_late15', 'mg_late18', 'mg_late21', 'mg_late24', 'mg_vs_only'):
        R = A if arm == 'mg_vs' else B if arm == 'mg_vs_only' else load(hook, arm)
        ok = [ep for ep in eps if ep in R and ep in A and ep in B]
        if not ok:
            continue
        m = [-R[ep]['margin'] for ep in ok]
        g = [(-R[ep]['margin']) - (-A[ep]['margin']) for ep in ok]
        gap = [(-B[ep]['margin']) - (-A[ep]['margin']) for ep in ok]
        lo, hi = ci(g) if any(g) else (0, 0)
        dead = sum((R[ep].get('rival_report') or {}).get('hamming_max', 0) for ep in ok) / len(ok)
        late = sum(1 for ep in ok if any(h[0] > 12 and (i == 0 or h[1] != R[ep]['rival_history'][i - 1][1])
                                         for i, h in enumerate(R[ep].get('rival_history') or [])))
        print(f'{arm:<12} {len(ok):>4} {sum(x > 0 for x in m):>7}-{sum(x < 0 for x in m):<8} {sum(m) / len(m):>+12,.0f} | '
              f'{sum(g) / len(g):>+12,.0f} ({lo:>+7,.0f} to {hi:>+7,.0f})        {sum(x > 0 for x in g):>5}/{sum(x < 0 for x in g):<7} | '
              f'{sum(g) / max(1, sum(gap)):>22.0%}  | {dead:>9.1f} {late:>11}')


if __name__ == '__main__':
    main()
