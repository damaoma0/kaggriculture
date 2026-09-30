"""Revenue/spend gap by product vs the targets, summed over all games of a tag."""
import gzip, json, sys
from collections import Counter
from pathlib import Path
tag = sys.argv[1]
R, TR, S, TS, U, TU = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
H, TH = Counter(), Counter()
n = 0
for f in sorted(Path(f'results/fresh/lead_agent_20260924/{tag}').glob('1*.json')):
    r = json.load(open(f)); n += 1
    team = r['game'].split(':')[0]
    sem = json.load(gzip.open(f'data/leader_semantics/{team}/{r["episode"]}.json.gz', 'rt'))
    for d in range(30):
        dd = r['days'][d]
        R.update(dd['rev']); S.update(dd['spend']); U.update(dd['sold']); H.update(dd['harv'])
        TH.update(sem['days'][d]['harvested']['units'])
    for dd in sem['days']:
        TR.update(dd['market']['sold_revenue']); TS.update(dd['market']['bought_spend']); TU.update(dd['market']['sold_units'])
print(f'{n} games; revenue ours {sum(R.values())/n:.0f} target {sum(TR.values())/n:.0f}; spend ours {sum(S.values())/n:.0f} target {sum(TS.values())/n:.0f} (per game)')
for p in sorted(set(R) | set(TR), key=lambda p: -(TR[p] - R[p])):
    print(f'  {p:11s} rev gap {(R[p]-TR[p])/n:8.0f}  units sold {U[p]/n:6.1f} vs {TU[p]/n:6.1f}  harvested {H[p]/n:6.1f} vs {TH[p]/n:6.1f}  price {R[p]/max(1,U[p]):6.1f} vs {TR[p]/max(1,TU[p]):6.1f}')
for p in sorted(set(S) | set(TS), key=lambda p: -abs(TS[p] - S[p])):
    print(f'  buy {p:9s} spend gap {(S[p]-TS[p])/n:8.0f}')
