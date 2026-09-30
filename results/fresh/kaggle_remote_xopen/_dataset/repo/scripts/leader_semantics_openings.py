import gzip, json, glob, collections
from pathlib import Path
names={'16915014':'Boey','16623559':'DECEM','16681125':'MMPQ','16730612':'MG','16770421':'Vadim','16732748':'DSM'}
games=collections.defaultdict(list)
for f in glob.glob('data/leader_semantics/*/*.json.gz'):
    games[Path(f).parent.name].append(json.load(gzip.open(f,'rt')))
d6={t:collections.Counter(''.join(g['days'][6]['board']) for g in gs) for t,gs in games.items()}
allb=collections.Counter()
for t,c in d6.items():
    allb.update(c); top=c.most_common(1)[0]
    print(f"{names[t]:6s} n={len(games[t])} distinct day-6 boards {len(c):2d}, modal share {top[1]/len(games[t]):.0%}")
print('cross-team top day-6 boards (count):', [n for b,n in allb.most_common(4)])
for t,gs in games.items():
    c=collections.Counter()
    for g in gs: c.update({k:v for k,v in g['days'][6]['board_counts'].items() if k not in (' .',' L')})
    print(f"{names[t]:6s} day-6 mean counts:", {k: round(v/len(gs),1) for k,v in sorted(c.items())})
