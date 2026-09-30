"""Extract observed production and daily tile occupancy, separately from requested work."""
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/umg_production'
CODES = {'WHEAT':'W','CARROT':'C','TOMATO':'T','STRAWBERRY':'S','MELON':'M','COW':'c','SHEEP':'s','GOOSE':'g'}

def code(t):
    if not isinstance(t, dict): return 'L' if t == 'LOCKED' else '.'
    return CODES.get(t.get('crop') or t.get('animal'), 'x' if t.get('kind') == 'WEED' else '.')

def extract(p):
    r=json.loads(p.read_text(encoding='utf-8'))
    names=r['info']['TeamNames']
    if 'Unknown Mother-Goose' not in names: return None
    s=names.index('Unknown Mother-Goose'); steps=r['steps']
    ds=[dict(planted={},harvest={},fert=0,work={},hands=0) for _ in range(30)]
    boards=[]; shops=[]
    for day in range(30):
        o=steps[day*24][s]['observation']
        boards.append(''.join(code(t) for row in o['farms'][s]['tiles'] for t in row))
        shops.append(o['town']['unlocked_shops'])
    for t in range(719):
        b=steps[t][s]['observation']; a=steps[t+1][s]['observation']; act=steps[t+1][s].get('action') or {}
        if not isinstance(act,dict): continue
        day=ds[t//24]; farm=b['farms'][s]; positions=[farm['farmer']]+farm['hands']
        day['hands']=max(day['hands'],len(a['farms'][s]['hands']))
        commands=[act.get('farmer')]+(act.get('hands') or [])
        for u,cmd in enumerate(commands):
            if not cmd or u>=len(positions): continue
            op=cmd[0];day['work'][op]=day['work'].get(op,0)+1
            x,y=positions[u]; before=farm['tiles'][y][x]; after=a['farms'][s]['tiles'][y][x]
            if op=='PLANT' and isinstance(after,dict) and after.get('crop') and (not isinstance(before,dict) or not before.get('crop')):
                k=after['crop'];day['planted'][k]=day['planted'].get(k,0)+1
            bi=b['private']['inventories']; ai=a['private']['inventories']
            if u>=len(bi) or u>=len(ai): continue
            if op=='HARVEST':
                for k,v in ai[u].items():
                    n=v-bi[u].get(k,0)
                    if n>0:day['harvest'][k]=day['harvest'].get(k,0)+n
            if op=='FERTILIZE':day['fert']+=max(0,bi[u].get('FERTILIZER',0)-ai[u].get('FERTILIZER',0))
    audit=json.loads((ROOT/f"results/fresh/leader_segments/segments-{r['info']['EpisodeId']}.json").read_text(encoding='utf-8'))
    segments=[]
    for seg in audit['seats'][s]['segments']:
        p=seg['physical']
        segments.append(dict(planted={k.split(':')[1]:v for k,v in p.items() if k.startswith('planted:')},harvest={k.split(':')[1]:v for k,v in p.items() if k.startswith('produced:') and k!='produced:FERTILIZER'},fert=p.get('fertilizer_applied',0)))
    return dict(id=r['info']['EpisodeId'],opponent=names[1-s],seat=s,cash=r['rewards'][s],boards=boards,shops=shops,days=ds,segments=segments)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    games=[]
    for p in sorted((ROOT/'data/leaders_20260917').glob('*.json')):
        g=extract(p)
        if g: games.append(g)
    data=dict(games=games,codes=CODES,source='September 17 replay sample; submission identity verified separately')
    (OUT/'data.json').write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
    template=(ROOT/'scripts/fragments/umg_production.html').read_text(encoding='utf-8')
    target=Path('C:/Users/xyygl/.codex/visualizations/2026/09/15/01a0a5c7-18b1-7141-a48f-45f175aa1a3c/umg-production-plans.html')
    target.write_text(template.replace('__DATA__',json.dumps(data,separators=(',',':'))),encoding='utf-8')
    assert target.stat().st_size<1000000
    print(json.dumps(dict(games=len(games),bytes=target.stat().st_size,path=str(target))))

if __name__=='__main__':main()
