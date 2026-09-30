"""xfix: paired full-game deltas on the clean worlds (the replayed opponent keeps >= 0.8x its recorded cash in both arms)."""
import glob, json, math, os, sys
from scipy import stats
T = {}
for d in ('results/fresh/xopen_20260925/g1/T', 'results/fresh/xfix_20260925/full/T'):
    for f in glob.glob(d + '/*.json'):
        r = json.load(open(f)); T[r['episode']] = r
for arm in sys.argv[1].split(','):
    A = {json.load(open(f))['episode']: json.load(open(f)) for f in glob.glob(f'results/fresh/xfix_20260925/full/{arm}/*.json')}
    es = [e for e in A if e in T and A[e]['opp_final'] >= 0.8 * A[e]['target_opp'] and T[e]['opp_final'] >= 0.8 * T[e]['target_opp']]
    d = [A[e]['final'] - T[e]['final'] for e in es]
    o = [A[e]['opp_final'] - T[e]['opp_final'] for e in es]
    n = len(d); m = sum(d) / n; s = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1)); h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    print(f'{arm}: clean {n}/{len(A)} worlds: own {m:+,.0f} ({m - h:+,.0f}..{m + h:+,.0f}), better {sum(x > 0 for x in d)}/{n}; '
          f'rival {sum(o) / n:+,.0f}; margin {m - sum(o) / n:+,.0f}')
