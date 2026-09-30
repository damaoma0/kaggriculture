"""xfix port checks (stored results): the ported agents/mgt_lead.py and agents/mgt_lead_deploy.py with the new options
off equal the previous files to the dollar; the new T defaults equal the measured arm; the deploy smoke with the pair on."""
import glob, json, math
from scipy import stats


def load(d, key='episode'):
    return {json.load(open(f))[key]: json.load(open(f)) for f in glob.glob(d + '/*.json')}


def same(A, B, fk='final', ok2=None):
    es = sorted(set(A) & set(B))
    good = [e for e in es if abs(A[e][fk] - B[e][fk]) < 0.5 and (ok2 is None or ok2(A[e], B[e]))]
    return len(good), len(es)


X = 'results/fresh/xfix_20260925/full'
T = load('results/fresh/xopen_20260925/g1/T')
days = lambda a, b: all(x.get('cash') == y.get('cash') for x, y in zip(a['days'], b['days']))
print('mgt_lead.py, pair off + xopen T settings == previous T (12 G1, final + every day-start cash): %d/%d' % same(load(X + '/Pold'), T, ok2=days))
G = {}
for f in glob.glob('results/fresh/lead_agent_20260924/abl_Gnew_remote/*.json'):
    r = json.load(open(f)); G[r['episode']] = r
print('mgt_lead.py, pair off + its own defaults == stored lead_ablation Gnew (12 G1): %d/%d' % same(load(X + '/Pdefoff'), G))
print('mgt_lead.py new defaults (pair on) == measured Fhmrp8 (12 G1): %d/%d' % same(load(X + '/Pnew'), load(X + '/Fhmrp8'), ok2=days))
E = 'results/fresh/xopen_20260925/e2'
N, P, O = load(E + '/mgt_lead_deploy'), load(E + '/mgt_lpv_xfprev'), load(E + '/mgt_lpv_xfon')
print('deploy, new options off == pre-port deploy (12 smoke, own and rival final): %d/%d' % same(N, P, ok2=lambda a, b: abs(a['rival'] - b['rival']) < 0.5))
es = sorted(set(O) & set(P))
d = [O[e]['margin'] - P[e]['margin'] for e in es]
m = sum(d) / len(d); s = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1)); h = stats.t.ppf(0.975, len(d) - 1) * s / math.sqrt(len(d))
own = sum(O[e]['final'] - P[e]['final'] for e in es) / len(es)
riv = sum(O[e]['rival'] - P[e]['rival'] for e in es) / len(es)
brk = sum(1 for e in es if O[e]['opp_dead'] - P[e]['opp_dead'] > 40)
print(f'deploy smoke, pair ON vs off: margin {m:+,.0f} (t {m - h:+,.0f}..{m + h:+,.0f}), better {sum(x > 0 for x in d)}/{len(d)}; own {own:+,.0f}, rival {riv:+,.0f}; opp tape broken {brk}')
mel = lambda R: sum(sum(v.get('MELON', 0) for v in R['revenue_daily']) for R in [R]) if 'revenue_daily' in R else 0
print('   melon revenue per game: pair on %.0f vs off %.0f' % (sum(mel(O[e]) for e in es) / len(es), sum(mel(P[e]) for e in es) / len(es)))
