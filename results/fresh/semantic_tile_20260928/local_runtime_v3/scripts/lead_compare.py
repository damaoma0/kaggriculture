"""Compare our G1 run with the target: revenue/spend per product (whole game and per day range)."""
import gzip, json, sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
tag, ep = sys.argv[1], sys.argv[2]
r = json.load(open(ROOT / f'results/fresh/lead_agent_20260924/{tag}/{ep}.json'))
team = r['game'].split(':')[0]
sem = json.load(gzip.open(ROOT / f'data/leader_semantics/{team}/{ep}.json.gz', 'rt'))
def tgt(day, key):  # actual-day market of target
    if day == 0: return Counter()
    i = 0 if day == 1 else day - 1
    c = Counter(sem['days'][i]['market'][key])

    return c
ranges = [(0, 6), (7, 12), (13, 20), (21, 29)]
if len(sys.argv) > 3:
    ranges = [tuple(map(int, x.split('-'))) for x in sys.argv[3].split(',')]
for a, b in ranges:
    ours_r, ours_s, t_r, t_s, ou, tu = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    for d in range(a, b + 1):
        ours_r.update(r['days'][d]['rev']); ou.update(r['days'][d]['sold'])
        ours_s.update(r['days'][d]['spend'])
        t_r.update(tgt(d, 'sold_revenue')); tu.update(tgt(d, 'sold_units'))
        t_s.update(tgt(d, 'bought_spend'))
    print(f'days {a}-{b}: revenue ours {sum(ours_r.values()):.0f} target {sum(t_r.values()):.0f}; spend ours {sum(ours_s.values()):.0f} target {sum(t_s.values()):.0f}')
    for p in sorted(set(ours_r) | set(t_r), key=lambda p: -(t_r[p])):
        print(f'   {p:11s} units {ou[p]:4d} vs {tu[p]:4d}  rev {ours_r[p]:7.0f} vs {t_r[p]:7.0f}')
    for p in sorted(set(ours_s) | set(t_s), key=lambda p: -(t_s[p])):
        print(f'   buy {p:9s} {ours_s[p]:7.0f} vs {t_s[p]:7.0f}')
