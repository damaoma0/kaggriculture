import gzip, json, glob, collections
from pathlib import Path
names={'16915014':'Boey','16623559':'DECEM','16681125':'MMPQ','16730612':'MG','16770421':'Vadim','16732748':'DSM'}
games=collections.defaultdict(list)
for f in glob.glob('data/leader_semantics/*/*.json.gz'):
    games[Path(f).parent.name].append(json.load(gzip.open(f,'rt')))
def labels(board):
    if isinstance(board, list) and board and len(board[0]) == 2: return board
    s=''.join(board); return [s[i:i+2] for i in range(0,len(s),2)]
CROP={'ST':'STRAW','TO':'TOMATO','ME':'MELON','WH':'WHEAT','CA':'CARROT'}
AN={'sh':'SHEEP','co':'COW','go':'GOOSE'}
def phase(d): return 'd0-6' if d<7 else ('d7-17' if d<18 else 'd18-29')
out=collections.defaultdict(lambda: collections.Counter())
yarn=collections.defaultdict(lambda: collections.Counter())
for t,gs in games.items():
    for g in gs:
        rev={s['reveal_day'] for s in g['shops'] if s['shop']=='YARN_STORE'}
        for d,day in enumerate(g['days']):
            lab=labels(day['board']); m=day['maintenance']
            W,F,C=set(m.get('WATER',[])),set(m.get('FEED',[])),set(m.get('CARE',[]))
            ph=phase(d)
            for j,x in enumerate(lab):
                if x in CROP:
                    out[(t,ph,CROP[x])]['n']+=1; out[(t,ph,CROP[x])]['w']+= j in W
                if x in AN:
                    k=(t,ph,AN[x]); out[k]['n']+=1; out[k]['f']+= j in F; out[k]['c']+= j in C
                    if x=='sh':
                        yv = any(r<=d for r in rev)
                        yarn[(t,yv)]['n']+=1; yarn[(t,yv)]['f']+= j in F; yarn[(t,yv)]['c']+= j in C
print('WATER share of crop tiles watered (day-start crops), by team / phase:')
for crop in ('STRAW','TOMATO','MELON','WHEAT','CARROT'):
    row=[]
    for t in names:
        for ph in ('d0-6','d7-17','d18-29'):
            c=out[(t,ph,crop)]
            row.append(f"{c['w']/c['n']:.2f}" if c['n']>20 else '  - ')
    print(f"  {crop:7s}", ' | '.join(' '.join(row[i:i+3]) for i in range(0,len(row),3)))
print('  teams:', ' | '.join(names[t] for t in names), ' (each: d0-6 d7-17 d18-29)')
print('FEED / CARE share of animal tiles:')
for sp in ('SHEEP','COW','GOOSE'):
    row=[]
    for t in names:
        for ph in ('d7-17','d18-29'):
            c=out[(t,ph,sp)]
            row.append(f"{c['f']/c['n']:.2f}/{c['c']/c['n']:.2f}" if c['n']>20 else '   -   ')
    print(f"  {sp:6s}", ' | '.join(' '.join(row[i:i+2]) for i in range(0,len(row),2)))
print('SHEEP feed/care with Yarn Store visible vs not:')
for t in names:
    a,b=yarn[(t,False)],yarn[(t,True)]
    fmt=lambda c: f"{c['f']/c['n']:.2f}/{c['c']/c['n']:.2f} (n={c['n']})" if c['n'] else '-'
    print(f"  {names[t]:6s} no Yarn {fmt(a)}   Yarn {fmt(b)}")
